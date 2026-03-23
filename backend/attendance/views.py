"""
backend/attendance/views.py

Attendance ViewSet + report endpoints.

Endpoint map (all under /api/attendance/):
  POST   sessions/start/                  → create session + pre-populate records
  GET    sessions/{id}/                   → session detail with records
  PATCH  sessions/{id}/submit/            → bulk-upsert records
  PATCH  sessions/{id}/finalize/          → lock session
  GET    sessions/report/?student=&term=  → student attendance summary
  GET    sessions/class-report/?class_arm=&term= → class heatmap data
  GET    sessions/low-attendance/?term=&threshold=75 → flagged students

Tenant scoping is guaranteed by TenantMixin on every ViewSet.
"""

import csv
from io import StringIO

from django.db.models import Count, Q, Avg
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tenants.mixins import TenantMixin
from .models import AttendanceSession, AttendanceRecord
from .serializers import (
    AttendanceSessionSerializer,
    AttendanceSessionCreateSerializer,
    BulkSubmitSerializer,
    StudentAttendanceSummarySerializer,
    DailyClassRecordSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _session_qs(school):
    return (
        AttendanceSession.objects
        .filter(school=school)
        .select_related('class_arm', 'teacher', 'term', 'period')
        .prefetch_related('records__student__profile')
    )


def _build_student_summary(school, student_id, term_id):
    """Returns the summary dict for a single student in a term."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        student = User.objects.select_related('profile__class_arm').get(
            pk=student_id, school=school
        )
    except User.DoesNotExist:
        return None

    summary = AttendanceRecord.objects.summary(student_id, term_id)
    return {
        'student_id':   student.id,
        'student_name': student.get_full_name() or student.username,
        'admission_no': getattr(getattr(student, 'profile', None), 'admission_number', ''),
        'class_arm':    str(getattr(getattr(student, 'profile', None), 'class_arm', '')),
        **summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# AttendanceSessionViewSet
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceSessionViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Core attendance CRUD + marking + reporting actions.
    """
    permission_classes = [IsAuthenticated]
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'start':
            return AttendanceSessionCreateSerializer
        return AttendanceSessionSerializer

    def get_queryset(self):
        qs   = _session_qs(self.school)
        term = self.request.query_params.get('term')
        if term:
            qs = qs.filter(term_id=term)
        return qs

    # ── POST sessions/start/ ─────────────────────────────────────────────────

    @action(detail=False, methods=['post'], url_path='start')
    def start(self, request):
        """
        Create a new AttendanceSession and pre-populate records.
        Returns the full session with the pre-built student list.
        """
        ser = AttendanceSessionCreateSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        ser.is_valid(raise_exception=True)
        session = ser.save()

        return Response(
            AttendanceSessionSerializer(
                session, context=self.get_serializer_context()
            ).data,
            status=status.HTTP_201_CREATED,
        )

    # ── PATCH sessions/{id}/submit/ ───────────────────────────────────────────

    @action(detail=True, methods=['patch'], url_path='submit')
    def submit(self, request, pk=None):
        """
        Bulk-upsert attendance records for a session.
        Body: { "records": [{student_id, status, remark?}, ...] }
        Idempotent — re-submitting overwrites previous marks.
        Blocked if the session is already finalized.
        """
        session = self.get_object()

        if session.is_finalized:
            return Response(
                {'detail': 'This session has been finalized and cannot be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = BulkSubmitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        records_data = ser.validated_data['records']
        student_ids  = [r['student_id'] for r in records_data]

        # Validate all students belong to this tenant
        from django.contrib.auth import get_user_model
        User = get_user_model()
        valid_ids = set(
            User.objects.filter(pk__in=student_ids, school=self.school)
            .values_list('id', flat=True)
        )

        # Bulk upsert using update_or_create
        updated, created = 0, 0
        for item in records_data:
            sid = item['student_id']
            if sid not in valid_ids:
                continue
            _, was_created = AttendanceRecord.objects.update_or_create(
                attendance_session=session,
                student_id=sid,
                defaults={'status': item['status'], 'remark': item.get('remark', '')},
            )
            if was_created:
                created += 1
            else:
                updated += 1

        return Response(
            AttendanceSessionSerializer(
                session, context=self.get_serializer_context()
            ).data
        )

    # ── PATCH sessions/{id}/finalize/ ─────────────────────────────────────────

    @action(detail=True, methods=['patch'], url_path='finalize')
    def finalize(self, request, pk=None):
        """
        Lock the session. Cannot be undone by teachers (admin can via Django admin).
        All students must have a record before finalization is permitted.
        """
        session = self.get_object()

        if session.is_finalized:
            return Response({'detail': 'Session is already finalized.'})

        # Guard: ensure every enrolled student has a record
        total_enrolled = session.class_arm.students.filter(school=self.school).count()
        total_marked   = session.records.count()

        if total_marked < total_enrolled:
            return Response(
                {
                    'detail': (
                        f'{total_enrolled - total_marked} student(s) have not been '
                        'marked yet. Please mark all students before finalizing.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        session.is_finalized = True
        session.save(update_fields=['is_finalized'])

        return Response({'detail': 'Session finalized successfully.', 'id': session.id})

    # ── GET sessions/report/?student=&term= ───────────────────────────────────

    @action(detail=False, methods=['get'], url_path='report')
    def report(self, request):
        """
        Per-student attendance summary for a term.
        """
        student_id = request.query_params.get('student')
        term_id    = request.query_params.get('term')

        if not (student_id and term_id):
            return Response(
                {'detail': 'Both student and term parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        summary = _build_student_summary(self.school, student_id, term_id)
        if summary is None:
            return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(summary)

    # ── GET sessions/class-report/?class_arm=&term= ───────────────────────────

    @action(detail=False, methods=['get'], url_path='class-report')
    def class_report(self, request):
        """
        Daily attendance summary for an entire class in a term.
        Returns list of sessions with counts — used to build the admin heatmap.
        Also supports ?format=csv for CSV download.
        """
        class_arm_id = request.query_params.get('class_arm')
        term_id      = request.query_params.get('term')

        if not (class_arm_id and term_id):
            return Response(
                {'detail': 'class_arm and term parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sessions = (
            AttendanceSession.objects
            .filter(school=self.school, class_arm_id=class_arm_id, term_id=term_id)
            .order_by('date', 'period__order_index')
            .annotate(
                total_students = Count('records'),
                present_count  = Count('records', filter=Q(records__status='present')),
                absent_count   = Count('records', filter=Q(records__status='absent')),
                late_count     = Count('records', filter=Q(records__status='late')),
            )
        )

        rows = []
        for s in sessions:
            total = s.total_students or 0
            effective = (s.present_count or 0) + (s.late_count or 0)
            rows.append({
                'date':           s.date,
                'period_name':    s.period.name if s.period else None,
                'total_students': total,
                'present_count':  s.present_count,
                'absent_count':   s.absent_count,
                'late_count':     s.late_count,
                'is_finalized':   s.is_finalized,
                'session_id':     s.id,
                'present_ratio':  round(effective / total, 3) if total else 0.0,
            })

        # Optional CSV export
        if request.query_params.get('format') == 'csv':
            return _export_class_report_csv(rows, class_arm_id)

        return Response(rows)

    # ── GET sessions/low-attendance/?term=&threshold= ─────────────────────────

    @action(detail=False, methods=['get'], url_path='low-attendance')
    def low_attendance(self, request):
        """
        Returns all students in a term whose attendance % < threshold (default 75).
        """
        term_id   = request.query_params.get('term')
        threshold = float(request.query_params.get('threshold', 75))

        if not term_id:
            return Response({'detail': 'term parameter is required.'}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get all students in this school
        students = User.objects.filter(school=self.school, role='student').select_related(
            'profile__class_arm'
        )

        flagged = []
        for student in students:
            summary = AttendanceRecord.objects.summary(student.id, term_id)
            if summary['total'] > 0 and summary['percentage'] < threshold:
                flagged.append({
                    'student_id':   student.id,
                    'student_name': student.get_full_name() or student.username,
                    'admission_no': getattr(getattr(student, 'profile', None), 'admission_number', ''),
                    'class_arm':    str(getattr(getattr(student, 'profile', None), 'class_arm', '')),
                    **summary,
                })

        # Sort by percentage ascending (worst first)
        flagged.sort(key=lambda x: x['percentage'])
        return Response({'count': len(flagged), 'threshold': threshold, 'students': flagged})


# ─────────────────────────────────────────────────────────────────────────────
# CSV export helper
# ─────────────────────────────────────────────────────────────────────────────

def _export_class_report_csv(rows, class_arm_id):
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        'date', 'period_name', 'total_students',
        'present_count', 'absent_count', 'late_count', 'is_finalized',
    ])
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row[k] for k in writer.fieldnames})

    response = HttpResponse(buf.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = (
        f'attachment; filename="attendance_class_{class_arm_id}.csv"'
    )
    return response