"""
backend/promotion/views.py

GET/POST /api/promotion/criteria/
POST     /api/promotion/evaluate/?session=&class_level=
POST     /api/promotion/execute/
"""

import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from .models import PromotionCriteria, PromotionRecord
from .services import evaluate_student


class PromotionCriteriaView(APIView):
    permission_classes = [IsAuthenticated]

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
        obj, _ = PromotionCriteria.objects.update_or_create(
            school=school,
            class_level_id=d['class_level_id'],
            defaults={
                'min_subjects_to_pass': d.get('min_subjects_to_pass', 5),
                'min_average_score':    d.get('min_average_score', 40),
                'min_attendance_pct':   d.get('min_attendance_pct', 50),
                'auto_promote_if_met':  d.get('auto_promote_if_met', False),
            },
        )
        return Response({'id': obj.id}, status=201)


class PromotionEvaluateView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school    = getattr(request, 'tenant', None)
        decisions = request.data
        from enrollment.models import StudentProfile, ClassArm
        from academics.models import AcademicSession

        records   = []
        graduates = []
        skipped   = []

        for item in decisions:
            try:
                student  = StudentProfile.objects.get(pk=item['student_id'], school=school)
                session  = AcademicSession.objects.get(pk=item['session_id'], school=school)
                to_class = ClassArm.objects.get(pk=item['to_class_id'], school=school) if item.get('to_class_id') else None
                next_sess = AcademicSession.objects.filter(school=school).order_by('-start_date').exclude(pk=session.pk).first()
            except Exception as exc:
                skipped.append({'student_id': item.get('student_id'), 'reason': str(exc)})
                continue

            if not student.current_class:
                skipped.append({'student_id': student.id, 'reason': 'Student has no class arm assigned'})
                continue

            PromotionRecord.objects.create(
                student=student,
                from_session=session,
                to_session=next_sess,
                from_class=student.current_class,
                to_class=to_class,
                decision=item['decision'],
                criteria_met=item.get('criteria_met', False),
                decided_by=request.user,
                notes=item.get('notes', ''),
                school=school,
            )
            records.append(item['student_id'])

            if item['decision'] == 'promoted' and to_class:
                student.current_class = to_class
                student.save(update_fields=['current_class'])
            elif item['decision'] == 'graduated':
                student.status = 'graduated'
                student.save(update_fields=['status'])
                graduates.append(student)

        if graduates:
            try:
                from notifications.services.termii import TermiiService
                svc = TermiiService()
                for s in graduates:
                    if s.guardian_phone:
                        msg = f"Congratulations! Your child has successfully graduated from {school.name}."
                        svc.send_sms(s.guardian_phone, msg, school.slug[:11], school=school, student=s)
            except Exception:
                logger.exception("Graduation SMS failed for school %s", getattr(school, 'id', None))

        return Response({'executed': len(records), 'graduated': len(graduates), 'skipped': skipped})
