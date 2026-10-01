from django.db import transaction
from accounts.school_access import SchoolModulePermission, require_assignment
"""
backend/promotion/views.py

GET/POST /api/promotion/criteria/
POST     /api/promotion/evaluate/?session=&class_level=
POST     /api/promotion/execute/
"""

import logging
from decimal import Decimal, InvalidOperation

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from .models import PromotionCriteria, PromotionRecord
from .services import evaluate_student


class PromotionCriteriaView(APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request):
        school = getattr(request, 'tenant', None)
        return Response([
            {
                'id': c.id,
                'class_level_id': c.class_level_id,
                'class_level_name': c.class_level.name,
                'min_subjects_to_pass': c.min_subjects_to_pass,
                'min_average_score': float(c.min_average_score),
                'min_attendance_pct': c.min_attendance_pct,
                'auto_promote_if_met': c.auto_promote_if_met,
            }
            for c in PromotionCriteria.objects.filter(school=school).select_related('class_level')
        ])

    def post(self, request):
        school = getattr(request, 'tenant', None)
        d      = request.data
        from enrollment.models import ClassLevel

        class_level = ClassLevel.objects.filter(pk=d.get('class_level_id'), school=school).first()
        if not class_level:
            return Response({'class_level_id': 'Choose a class level belonging to this school.'}, status=400)

        try:
            min_subjects = int(d.get('min_subjects_to_pass', 5))
            min_average = Decimal(str(d.get('min_average_score', 40)))
            min_attendance = int(d.get('min_attendance_pct', 50))
        except (TypeError, ValueError, InvalidOperation):
            return Response({'detail': 'Enter valid promotion criteria numbers.'}, status=400)

        errors = {}
        if min_subjects < 0 or min_subjects > 30:
            errors['min_subjects_to_pass'] = 'Enter a value between 0 and 30.'
        if min_average < 0 or min_average > 100:
            errors['min_average_score'] = 'Enter a percentage between 0 and 100.'
        if min_attendance < 0 or min_attendance > 100:
            errors['min_attendance_pct'] = 'Enter a percentage between 0 and 100.'
        if errors:
            return Response(errors, status=400)

        obj, _ = PromotionCriteria.objects.update_or_create(
            school=school,
            class_level=class_level,
            defaults={
                'min_subjects_to_pass': min_subjects,
                'min_average_score':    min_average,
                'min_attendance_pct':   min_attendance,
                'auto_promote_if_met':  bool(d.get('auto_promote_if_met', False)),
            },
        )
        return Response({'id': obj.id}, status=201)


class PromotionEvaluateView(APIView):
    permission_classes = [SchoolModulePermission]

    def post(self, request):
        school         = getattr(request, 'tenant', None)
        session_id     = request.query_params.get('session')
        class_level_id = request.query_params.get('class_level')
        from academics.models import AcademicSession
        from enrollment.models import SessionEnrollment, StudentProfile

        try:
            session = AcademicSession.objects.get(pk=session_id, school=school)
        except AcademicSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)

        enrollments = SessionEnrollment.objects.filter(
            school=school,
            session=session,
            status='active',
        ).select_related(
            'student__user',
            'class_arm__class_level',
        )
        if class_level_id:
            enrollments = enrollments.filter(
                class_arm__class_level_id=class_level_id
            )

        criteria_map = {
            c.class_level_id: c
            for c in PromotionCriteria.objects.filter(
                school=school
            ).select_related('class_level')
        }

        results = []
        enrolled_student_ids = set()
        for enrollment in enrollments:
            student = enrollment.student
            enrolled_student_ids.add(student.pk)
            if student.status != 'active' or enrollment.status != 'active':
                continue
            level = enrollment.class_arm.class_level
            criteria = criteria_map.get(level.pk) or PromotionCriteria(
                school=school,
                class_level=level,
            )
            row = evaluate_student(
                student,
                session,
                criteria,
                class_arm=enrollment.class_arm,
            )
            row['membership_source'] = 'session_enrollment'
            results.append(row)

        # Compatibility is intentionally limited to the current session.
        # Older sessions must have explicit SessionEnrollment history.
        if session.is_current:
            missing = StudentProfile.objects.filter(
                school=school,
                status='active',
                current_class__isnull=False,
            ).exclude(pk__in=enrolled_student_ids).select_related(
                'user',
                'current_class__class_level',
            )
            if class_level_id:
                missing = missing.filter(
                    current_class__class_level_id=class_level_id
                )
            for student in missing:
                level = student.current_class.class_level
                criteria = criteria_map.get(level.pk) or PromotionCriteria(
                    school=school,
                    class_level=level,
                )
                row = evaluate_student(
                    student,
                    session,
                    criteria,
                    class_arm=student.current_class,
                )
                row['membership_source'] = 'current_class_compatibility'
                results.append(row)

        return Response(results)


class PromotionExecuteView(APIView):
    permission_classes = [SchoolModulePermission]

    @transaction.atomic
    def post(self, request):
        from enrollment.models import StudentProfile, ClassArm, SessionEnrollment
        from academics.models import AcademicSession
        from tenants.models import School, PlatformEvent
        from rest_framework.exceptions import ValidationError

        school = School.objects.select_for_update().get(pk=request.tenant.pk)
        decisions = request.data
        if not isinstance(decisions, list) or not decisions or len(decisions) > 1000:
            raise ValidationError('Provide between 1 and 1000 decisions.')

        seen, prepared = set(), []
        for item in decisions:
            if not isinstance(item, dict) or item.get('decision') not in dict(PromotionRecord.DECISION_CHOICES):
                raise ValidationError('Select a valid promotion decision.')

            sid = item.get('student_id')
            if sid in seen:
                raise ValidationError('A student occurs more than once.')
            seen.add(sid)

            student = StudentProfile.objects.select_for_update().filter(
                pk=sid,
                school=school,
                status='active',
            ).first()
            session = AcademicSession.objects.filter(
                pk=item.get('session_id'),
                school=school,
            ).first()
            if not student or not session:
                raise ValidationError(
                    'Select an active student and source session from this school.'
                )

            if PromotionRecord.objects.filter(
                school=school,
                student=student,
                from_session=session,
            ).exists():
                raise ValidationError(
                    'A decision already exists for this student and session. Review it before changing records.'
                )

            source_enrollment = SessionEnrollment.objects.select_for_update().filter(
                school=school,
                student=student,
                session=session,
                status='active',
            ).first()

            if not source_enrollment:
                if SessionEnrollment.objects.filter(
                    school=school,
                    student=student,
                    session=session,
                ).exists():
                    raise ValidationError(
                        'The session has enrollment history but no active final placement. Restore the enrollment history before promotion.'
                    )
                if not session.is_current or not student.current_class:
                    raise ValidationError(
                        'Historical class membership is missing for this session. Restore the session enrollment before promotion.'
                    )
                source_enrollment = SessionEnrollment.objects.create(
                    school=school,
                    student=student,
                    session=session,
                    class_arm=student.current_class,
                    status='active',
                    entry_reason='migration',
                    enrolled_on=min(max(student.admission_date, session.start_date), session.end_date),
                    notes='Compatibility enrollment created during Batch 19 promotion.',
                    created_by=request.user,
                )

            if source_enrollment.status != 'active':
                raise ValidationError('The source session enrollment is already closed.')

            source_arm = source_enrollment.class_arm
            decision = item['decision']
            destination = None
            destination_arm = None

            if decision in ('promoted', 'repeated'):
                destination = AcademicSession.objects.filter(
                    pk=item.get('to_session_id'),
                    school=school,
                    start_date__gt=session.end_date,
                ).first()
                if not destination:
                    raise ValidationError(
                        'Select an explicit destination session after the source session ends.'
                    )

                if SessionEnrollment.objects.filter(
                    student=student,
                    session=destination,
                ).exists():
                    raise ValidationError(
                        'This student already has an enrollment in the destination session.'
                    )

                if decision == 'promoted':
                    destination_arm = ClassArm.objects.select_related(
                        'class_level'
                    ).filter(
                        pk=item.get('to_class_id'),
                        school=school,
                    ).first()
                    if (
                        not destination_arm
                        or destination_arm.class_level.order_index
                        <= source_arm.class_level.order_index
                    ):
                        raise ValidationError(
                            'Promotion requires a higher destination class belonging to this school.'
                        )
                else:
                    destination_arm = source_arm

            prepared.append({
                'student': student,
                'session': session,
                'source_enrollment': source_enrollment,
                'source_arm': source_arm,
                'destination': destination,
                'destination_arm': destination_arm,
                'item': item,
            })

        for change in prepared:
            student = change['student']
            session = change['session']
            source_enrollment = change['source_enrollment']
            source_arm = change['source_arm']
            destination = change['destination']
            destination_arm = change['destination_arm']
            item = change['item']
            decision = item['decision']

            # Batch 19: year-end decisions are staged here only. Student placement,
            # lifecycle status, login activation, and destination enrollment are
            # applied exclusively by the atomic academic rollover executor.
            record = PromotionRecord.objects.create(
                school=school,
                student=student,
                from_session=session,
                to_session=destination,
                from_class=source_arm,
                to_class=destination_arm,
                decision=decision,
                criteria_met=bool(item.get('criteria_met', False)),
                decided_by=request.user,
                notes=str(item.get('notes', ''))[:2000],
            )

            PlatformEvent.objects.create(
                actor=request.user,
                actor_email=request.user.email,
                action='school.promotion_decision',
                target=str(record.pk),
                details={
                    'school_id': school.pk,
                    'student_id': student.pk,
                    'decision': decision,
                    'from_enrollment_id': source_enrollment.pk,
                    'to_session_id': destination.pk if destination else None,
                    'to_class_id': destination_arm.pk if destination_arm else None,
                    'staged': True,
                },
            )

        return Response({
            'staged': len(prepared),
            # Kept for older clients that still read the legacy field name.
            'executed': len(prepared),
            'applied': False,
            'graduated': sum(
                change['item']['decision'] == 'graduated'
                for change in prepared
            ),
            'skipped': [],
        })

