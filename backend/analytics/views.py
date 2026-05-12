"""
backend/analytics/views.py

GET  /api/analytics/overview/?term=
GET  /api/analytics/class/{pk}/?term=
GET  /api/analytics/student/{pk}/trends/?terms=4
POST /api/analytics/refresh/?term=
GET  /api/reports/transcript/{pk}/
"""

from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AnalyticsSnapshot
from .tasks import compute_school_analytics


class AnalyticsOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school  = getattr(request, 'tenant', None)
        term_id = request.query_params.get('term')
        if not term_id:
            from academics.models import Term
            term = Term.objects.filter(session__school=school, is_current=True).first()
            if not term:
                return Response({'error': 'No current term.'}, status=404)
            term_id = term.id
        snap = AnalyticsSnapshot.objects.filter(school=school, term_id=term_id).first()
        if not snap:
            return Response({'detail': 'No snapshot yet. POST /api/analytics/refresh/ to compute.'}, status=204)
        return Response({'computed_at': snap.computed_at, **snap.data})


class AnalyticsRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school  = getattr(request, 'tenant', None)
        if not school:
            return Response({'error': 'No school context.'}, status=400)
        term_id = request.query_params.get('term')
        if not term_id:
            from academics.models import Term
            term = Term.objects.filter(session__school=school, is_current=True).first()
            if not term:
                return Response({'error': 'No current term.'}, status=404)
            term_id = term.id
        compute_school_analytics.delay(school.id, int(term_id))
        return Response({'detail': 'Analytics computation queued.'})


class ClassAnalyticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        school  = getattr(request, 'tenant', None)
        term_id = request.query_params.get('term')
        from gradebook.models import ScoreEntry
        from enrollment.models import ClassArm
        try:
            arm = ClassArm.objects.get(pk=pk, school=school)
        except ClassArm.DoesNotExist:
            return Response(status=404)
        qs = ScoreEntry.objects.filter(school=school, class_arm=arm)
        if term_id:
            qs = qs.filter(term_id=term_id)
        subject_avgs = [
            {'subject': r['subject__name'], 'avg': round(float(r['avg']), 1)}
            for r in qs.values('subject__name').annotate(avg=Avg('total_score')).order_by('-avg')
        ]
        top_students = [
            {'name': f"{r['student__first_name']} {r['student__last_name']}", 'avg': round(float(r['avg']), 1)}
            for r in qs.values('student__first_name', 'student__last_name').annotate(avg=Avg('total_score')).order_by('-avg')[:10]
        ]
        return Response({'class': arm.full_name, 'subject_avgs': subject_avgs, 'top_students': top_students})


class StudentTrendsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        school    = getattr(request, 'tenant', None)
        num_terms = int(request.query_params.get('terms', 4))
        from enrollment.models import StudentProfile
        from academics.models import Term
        from gradebook.models import ScoreEntry
        from attendance.models import AttendanceRecord
        from results.models import ResultRemark

        try:
            student = StudentProfile.objects.get(pk=pk, school=school)
        except StudentProfile.DoesNotExist:
            return Response(status=404)

        terms  = list(reversed(list(Term.objects.filter(session__school=school).order_by('-session__start_date', '-name')[:num_terms])))
        result = []
        for term in terms:
            scores     = ScoreEntry.objects.filter(student=student.user, term=term, school=school)
            avg        = scores.aggregate(a=Avg('total_score'))['a']
            remark     = ResultRemark.objects.filter(student=student, term=term, school=school).first()
            attend     = AttendanceRecord.objects.filter(student=student.user, attendance_session__term=term, school=school).aggregate(
                present=Count('id', filter=Q(status='present')), total=Count('id')
            )
            attend_pct = round(attend['present'] / attend['total'] * 100) if attend['total'] else None
            result.append({
                'term_name':      f"{term.get_name_display()} {term.session.name}",
                'average':        round(float(avg), 1) if avg else None,
                'position':       remark.computed_position if remark else None,
                'subjects':       [{'subject': s['subject__name'], 'score': round(float(s['total_score']), 1)} for s in scores.values('subject__name', 'total_score').order_by('subject__name')],
                'attendance_pct': attend_pct,
            })
        return Response(result)


class TranscriptPDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        school = getattr(request, 'tenant', None)
        from enrollment.models import StudentProfile
        from academics.models import Term
        from gradebook.models import ScoreEntry
        from results.models import ResultRemark

        try:
            student = StudentProfile.objects.select_related('user', 'current_class').get(pk=pk, school=school)
        except StudentProfile.DoesNotExist:
            return Response(status=404)

        history = []
        for term in Term.objects.filter(session__school=school).order_by('session__start_date', 'name'):
            scores = ScoreEntry.objects.filter(student=student.user, term=term, school=school)
            if not scores.exists():
                continue
            avg    = scores.aggregate(a=Avg('total_score'))['a']
            remark = ResultRemark.objects.filter(student=student, term=term, school=school).first()
            history.append({
                'term':     term,
                'scores':   list(scores.select_related('subject').order_by('subject__name')),
                'average':  round(float(avg), 1) if avg else None,
                'position': remark.computed_position if remark else None,
            })

        try:
            from weasyprint import HTML
            html = render_to_string('analytics/cumulative_transcript.html', {
                'student': student, 'school': school, 'history': history,
            })
            pdf  = HTML(string=html).write_pdf()
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="transcript_{student.admission_number}.pdf"'
            return resp
        except Exception as exc:
            return Response({'error': str(exc)}, status=500)
