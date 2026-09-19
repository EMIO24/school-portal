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
        from enrollment.models import StudentProfile

        try:
            session = AcademicSession.objects.get(pk=session_id, school=school)
        except AcademicSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=404)

        students = StudentProfile.objects.filter(school=school, status='active').select_related('user', 'current_class__class_level')
        if class_level_id:
            students = students.filter(current_class__class_level_id=class_level_id)

        # Pre-load all criteria for this school in one query to avoid N+1
        criteria_map = {
            c.class_level_id: c
            for c in PromotionCriteria.objects.filter(school=school).select_related('class_level')
        }

        results = []
        for student in students:
            if not student.current_class:
                continue
            level_id = student.current_class.class_level_id
            criteria = criteria_map.get(level_id) or PromotionCriteria(
                school=school, class_level=student.current_class.class_level
            )
            results.append(evaluate_student(student, session, criteria))
        return Response(results)


class PromotionExecuteView(APIView):
    permission_classes = [SchoolModulePermission]

    @transaction.atomic
    def post(self, request):
        from enrollment.models import StudentProfile, ClassArm
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
            if sid in seen: raise ValidationError('A student occurs more than once.')
            seen.add(sid)
            student = StudentProfile.objects.select_for_update().filter(pk=sid, school=school, status='active').first()
            session = AcademicSession.objects.filter(pk=item.get('session_id'), school=school).first()
            if not student or not student.current_class or not session:
                raise ValidationError('Select an active student, current class and source session from this school.')
            existing = PromotionRecord.objects.filter(school=school, student=student, from_session=session).first()
            if existing:
                raise ValidationError('A decision already exists for this student and session. Review it before changing records.')
            destination = AcademicSession.objects.filter(pk=item.get('to_session_id'), school=school, start_date__gt=session.end_date).first()
            arm = ClassArm.objects.filter(pk=item.get('to_class_id'), school=school).first()
            decision = item['decision']
            if decision in ('promoted','repeated') and not destination:
                raise ValidationError('Select an explicit destination session after the source session ends.')
            if decision == 'promoted' and (not arm or arm.class_level.order_index <= student.current_class.class_level.order_index):
                raise ValidationError('Promotion requires a higher destination class.')
            if decision == 'repeated': arm = student.current_class
            if decision in ('graduated','withdrawn'): arm, destination = None, None
            prepared.append((student, session, destination, arm, item))
        for student, session, destination, arm, item in prepared:
            record = PromotionRecord.objects.create(school=school, student=student, from_session=session, to_session=destination, from_class=student.current_class, to_class=arm, decision=item['decision'], criteria_met=bool(item.get('criteria_met',False)), decided_by=request.user, notes=str(item.get('notes',''))[:2000])
            if item['decision'] in ('promoted','repeated'): student.current_class = arm
            else: student.status = item['decision']
            student.save(update_fields=['current_class','status'])
            PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email, action='school.promotion', target=str(record.pk), details={'school_id':school.pk,'student_id':student.pk,'decision':item['decision']})
        return Response({'executed':len(prepared),'graduated':sum(item['decision']=='graduated' for *_,item in prepared),'skipped':[]})
