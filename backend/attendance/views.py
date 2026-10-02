from accounts.school_access import assigned_classes
from accounts.school_access import SchoolModulePermission, require_assignment
from enrollment.enrollment_periods import (
    EnrollmentResolutionError,
    enrolled_user_ids_for_class_on_date,
    enrollment_for_term,
)
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
from datetime import date, datetime
from io import StringIO

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q, Avg
from django.utils import timezone
from django.http import HttpResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from tenants.mixins import TenantMixin
from tenants.document_branding import school_branding_context, secure_document_response
from .models import AttendanceSession, AttendanceRecord, StudentDailyPresence
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
        .prefetch_related('records__student__student_profile')
    )


def _build_student_summary(school, student_id, term_id):
    """Returns the summary dict for a single student in a term."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    try:
        student = User.objects.select_related('student_profile__current_class').get(
            pk=student_id, school=school
        )
    except User.DoesNotExist:
        return None

    summary = AttendanceRecord.objects.summary(student_id, term_id)
    profile = getattr(student, 'student_profile', None)
    class_label = ''
    if profile:
        from academics.models import Term
        term = Term.objects.select_related('session').filter(
            pk=term_id,
            session__school=school,
        ).first()
        if term:
            try:
                period = enrollment_for_term(
                    school=school,
                    student=profile,
                    term=term,
                )
                class_label = period.class_arm.full_name if period else ''
            except EnrollmentResolutionError:
                class_label = 'Multiple classes'
    return {
        'student_id':   student.id,
        'student_name': student.get_full_name() or student.username,
        'admission_no': getattr(profile, 'admission_number', ''),
        'class_arm':    class_label,
        **summary,
    }


# ─────────────────────────────────────────────────────────────────────────────
# AttendanceSessionViewSet
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceSessionViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Core attendance CRUD + marking + reporting actions.
    """
    permission_classes = [SchoolModulePermission]
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def create(self, request, *args, **kwargs):
        return self.start(request)

    def update(self, request, *args, **kwargs):
        from rest_framework.exceptions import ValidationError
        self.get_object()
        raise ValidationError('Use attendance marking to edit records. The class, term and date of an existing register cannot be moved.')

    def get_object(self):
        from accounts.school_access import require_assignment
        session = super().get_object()
        require_assignment(self.request, session.class_arm_id, session.term_id)
        return session

    def get_serializer_class(self):
        if self.action == 'start':
            return AttendanceSessionCreateSerializer
        return AttendanceSessionSerializer

    def get_queryset(self):
        qs   = _session_qs(self.school)
        term = self.request.query_params.get('term')
        if term:
            qs = qs.filter(term_id=term)
        if self.request.user.role in ("teacher", "class_teacher"):
            qs = qs.filter(class_arm_id__in=assigned_classes(self.request))
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

        # Validate membership against the class placement on this register's date.
        roster_ids = set(
            enrolled_user_ids_for_class_on_date(
                school=self.school,
                class_arm=session.class_arm,
                session=session.term.session,
                on_date=session.date,
            )
        )
        valid_ids = roster_ids.intersection(student_ids)

        if valid_ids != set(student_ids):
            return Response({'detail':'All students must belong to this class.'}, status=400)

        if session.mode == AttendanceSession.Mode.DAILY:
            existing_arrivals = set(
                StudentDailyPresence.objects.filter(
                    school=self.school,
                    student__user_id__in=valid_ids,
                    date=session.date,
                    arrival_at__isnull=False,
                ).values_list('student__user_id', flat=True)
            )
            for item in records_data:
                if (
                    item['status'] == AttendanceRecord.Status.LATE
                    and not item.get('arrival_time')
                    and item['student_id'] not in existing_arrivals
                ):
                    return Response(
                        {'detail': 'Enter an arrival time for every late student, or record their arrival in Student Presence first.'},
                        status=400,
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
            arrival_time = item.get('arrival_time')
            if session.mode == AttendanceSession.Mode.DAILY and item['status'] == AttendanceRecord.Status.LATE and arrival_time:
                from enrollment.models import StudentProfile
                profile = StudentProfile.objects.filter(school=self.school, user_id=sid).first()
                if profile:
                    naive = datetime.combine(session.date, arrival_time)
                    arrival_at = timezone.make_aware(naive, timezone.get_current_timezone())
                    presence, _ = StudentDailyPresence.objects.get_or_create(
                        school=self.school, student=profile, date=session.date,
                        defaults={'class_arm': session.class_arm},
                    )
                    if presence.class_arm_id is None:
                        presence.class_arm = session.class_arm
                    if presence.arrival_at is None:
                        presence.arrival_at = arrival_at
                        presence.arrival_recorded_by = request.user
                        presence.save(update_fields=['class_arm', 'arrival_at', 'arrival_recorded_by', 'updated_at'])
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

        # Guard: expected roster is the historical class membership on this date.
        enrolled = list(
            enrolled_user_ids_for_class_on_date(
                school=self.school,
                class_arm=session.class_arm,
                session=session.term.session,
                on_date=session.date,
            )
        )
        total_enrolled = len(enrolled)
        total_marked = session.records.filter(student_id__in=enrolled).count()

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

    # ── GET sessions/student-report/?student=&term= ──────────────────────────

    @action(detail=False, methods=['get'], url_path='student-report')
    def student_report(self, request):
        """
        Return only the attendance records belonging to one student
        for a specific term.

        Access is protected by SchoolModulePermission, which verifies
        that a student is requesting their own data or a parent is
        requesting data for a linked child.
        """
        student_id = request.query_params.get('student')
        term_id = request.query_params.get('term')

        if not (student_id and term_id):
            return Response(
                {'detail': 'Both student and term parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        records = (
            AttendanceRecord.objects
            .filter(
                attendance_session__school=self.school,
                student_id=student_id,
                attendance_session__term_id=term_id,
            )
            .select_related('attendance_session')
            .order_by('attendance_session__date')
        )

        return Response([
            {
                'date': record.attendance_session.date,
                'status': record.status,
                'remark': record.remark,
                'session_id': record.attendance_session_id,
            }
            for record in records
        ])

    # ── GET sessions/class-report/?class_arm=&term= ───────────────────────────

    @action(detail=False, methods=['get'], url_path='class-report')
    def class_report(self, request):
        """
        Daily attendance summary for an entire class in a term.
        Returns list of sessions with counts — used to build the admin heatmap.
        Also supports ?download=pdf for PDF download (legacy csv requests return PDF).
        """
        class_arm_id = request.query_params.get('class_arm')
        term_id      = request.query_params.get('term')

        if not (class_arm_id and term_id):
            return Response(
                {'detail': 'class_arm and term parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        require_assignment(request, class_arm_id, term_id)

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
        if request.query_params.get('download') in ('csv', 'pdf'):
            return _export_class_report_pdf(rows, class_arm_id, getattr(request, 'tenant', None))

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

        attendance = Q(attendance_records__attendance_session__school=self.school,
                       attendance_records__attendance_session__term_id=term_id)
        students = User.objects.filter(
            school=self.school, role='student', student_profile__status='active'
        ).select_related(
            'student_profile__current_class__class_level', 'student_profile__current_class__school'
        ).annotate(
            attendance_total=Count('attendance_records', filter=attendance),
            attendance_present=Count('attendance_records', filter=attendance & Q(attendance_records__status='present')),
            attendance_absent=Count('attendance_records', filter=attendance & Q(attendance_records__status='absent')),
            attendance_late=Count('attendance_records', filter=attendance & Q(attendance_records__status='late')),
            attendance_excused=Count('attendance_records', filter=attendance & Q(attendance_records__status='excused')),
        )

        flagged = []
        for student in students:
            denominator = max(student.attendance_total - student.attendance_excused, 0)
            percentage = round((student.attendance_present + student.attendance_late) / denominator * 100, 1) if denominator else 0.0
            if student.attendance_total > 0 and percentage < threshold:
                flagged.append({
                    'student_id':   student.id,
                    'student_name': student.get_full_name() or student.username,
                    'admission_no': getattr(getattr(student, 'student_profile', None), 'admission_number', ''),
                    'class_arm':    str(getattr(getattr(student, 'student_profile', None), 'current_class', '')),
                    'total': student.attendance_total,
                    'present': student.attendance_present,
                    'absent': student.attendance_absent,
                    'late': student.attendance_late,
                    'excused': student.attendance_excused,
                    'percentage': percentage,
                })

        # Sort by percentage ascending (worst first)
        flagged.sort(key=lambda x: x['percentage'])
        return Response({'count': len(flagged), 'threshold': threshold, 'students': flagged})


# ─────────────────────────────────────────────────────────────────────────────
# CSV export helper
# ─────────────────────────────────────────────────────────────────────────────

def _export_class_report_pdf(rows, class_arm_id, school=None):
    from results.report_pdf import text_report_pdf
    lines = []
    for row in rows:
        lines.extend([
            str(row['date']) + ' | ' + (row['period_name'] or 'Daily attendance'),
            'Students: ' + str(row['total_students']) + ' | Present: ' + str(row['present_count']) +
            ' | Absent: ' + str(row['absent_count']) + ' | Late: ' + str(row['late_count']),
            'Finalized: ' + ('Yes' if row['is_finalized'] else 'No'), '',
        ])
    branding = school_branding_context(school) if school else {}
    response = HttpResponse(text_report_pdf('Class attendance report', lines or ['No attendance records.'], branding=branding), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_class_{class_arm_id}.pdf"'
    return secure_document_response(response)


def _presence_actor_allowed(request, student, *, correction=False):
    role = request.user.role
    if role in ('school_admin', 'principal'):
        return True
    if correction:
        return False
    if role == 'class_teacher':
        return bool(student.current_class_id and student.current_class.class_teacher_id == request.user.pk)
    return False


def _presence_payload(presence, school):
    cutoff = school.arrival_cutoff_time
    local_arrival = timezone.localtime(presence.arrival_at) if presence.arrival_at else None
    local_departure = timezone.localtime(presence.departure_at) if presence.departure_at else None
    return {
        'id': presence.pk,
        'student_id': presence.student_id,
        'student_name': presence.student.full_name,
        'class_arm': presence.class_arm.full_name if presence.class_arm else (
            presence.student.current_class.full_name if presence.student.current_class else ''
        ),
        'date': presence.date,
        'arrival_at': local_arrival.isoformat() if local_arrival else None,
        'arrival_time': local_arrival.strftime('%H:%M') if local_arrival else None,
        'late': bool(local_arrival and cutoff and local_arrival.time().replace(tzinfo=None) > cutoff),
        'departure_at': local_departure.isoformat() if local_departure else None,
        'departure_time': local_departure.strftime('%H:%M') if local_departure else None,
        'clockout_enabled': school.student_clockout_enabled,
    }


class StudentPresenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'tenant', None)
        if not school or request.user.school_id != school.pk or request.user.role not in ('school_admin', 'principal', 'class_teacher'):
            return Response({'detail': 'School presence access required.'}, status=403)
        raw_date = request.query_params.get('date')
        try:
            on_date = date.fromisoformat(raw_date) if raw_date else timezone.localdate()
        except ValueError:
            return Response({'date': 'Use YYYY-MM-DD.'}, status=400)
        class_arm = request.query_params.get('class_arm')
        if not class_arm or not str(class_arm).isdigit():
            return Response({'class_arm': 'Choose a valid class.'}, status=400)
        from enrollment.models import ClassArm, StudentProfile
        arm = ClassArm.objects.filter(school=school, pk=class_arm).first()
        if not arm:
            return Response({'class_arm': 'Choose a class in this school.'}, status=400)
        if request.user.role == 'class_teacher' and arm.class_teacher_id != request.user.pk:
            return Response({'detail': 'This is not your class.'}, status=403)
        students = StudentProfile.objects.filter(
            school=school, status='active', current_class=arm
        ).select_related('user', 'current_class__class_level').order_by('user__last_name', 'user__first_name')
        presence_map = {
            row.student_id: row
            for row in StudentDailyPresence.objects.filter(
                school=school, date=on_date, student__in=students
            ).select_related('student__user', 'student__current_class__class_level', 'class_arm__class_level')
        }
        rows = []
        for student in students:
            presence = presence_map.get(student.pk)
            rows.append({
                'student_id': student.pk,
                'student_name': student.full_name,
                'admission_number': student.admission_number,
                'class_arm': arm.full_name,
                'presence': _presence_payload(presence, school) if presence else None,
            })
        return Response({'date': on_date, 'class_arm': arm.pk, 'class_name': arm.full_name, 'students': rows})

    @transaction.atomic
    def post(self, request):
        school = getattr(request, 'tenant', None)
        from enrollment.models import StudentProfile
        student = StudentProfile.objects.select_related('current_class__class_level').filter(
            pk=request.data.get('student'), school=school, status='active'
        ).first()
        if not school or not student or not _presence_actor_allowed(request, student):
            return Response({'detail': 'Student presence access denied.'}, status=403)
        now = timezone.now()
        presence, _ = StudentDailyPresence.objects.select_for_update().get_or_create(
            school=school, student=student, date=timezone.localdate(now),
            defaults={'class_arm': student.current_class},
        )
        if presence.class_arm_id is None:
            presence.class_arm = student.current_class
        if presence.arrival_at is None:
            presence.arrival_at = now
            presence.arrival_recorded_by = request.user
            presence.save(update_fields=['class_arm', 'arrival_at', 'arrival_recorded_by', 'updated_at'])
            from tenants.security import audit
            audit(request, 'attendance.student_arrival_recorded', target=f'presence:{presence.pk}',
                  details={'school_id': school.pk, 'student_id': student.pk})
        return Response(_presence_payload(presence, school), status=201)


class StudentClockOutView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        school = getattr(request, 'tenant', None)
        if not school or not school.student_clockout_enabled:
            return Response({'detail': 'Student clock-out is not enabled for this school.'}, status=403)
        from enrollment.models import StudentProfile
        student = StudentProfile.objects.select_related('current_class__class_level').filter(
            pk=request.data.get('student'), school=school, status='active'
        ).first()
        if not student or not _presence_actor_allowed(request, student):
            return Response({'detail': 'Student clock-out access denied.'}, status=403)
        presence = StudentDailyPresence.objects.select_for_update().select_related(
            'student__user', 'student__current_class__class_level', 'class_arm__class_level'
        ).filter(
            school=school, student=student, date=timezone.localdate()
        ).first()
        if not presence or not presence.arrival_at:
            return Response({'detail': 'Record the student arrival before clock-out.'}, status=409)
        if presence.departure_at is None:
            presence.departure_at = timezone.now()
            presence.departure_recorded_by = request.user
            presence.save(update_fields=['departure_at', 'departure_recorded_by', 'updated_at'])
            from tenants.security import audit
            audit(request, 'attendance.student_clocked_out', target=f'presence:{presence.pk}',
                  details={'school_id': school.pk, 'student_id': student.pk})
        return Response(_presence_payload(presence, school))


class StudentPresenceCorrectionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, pk):
        school = getattr(request, 'tenant', None)
        if not school or request.user.role not in ('school_admin', 'principal') or request.user.school_id != school.pk:
            return Response({'detail': 'Presence correction access denied.'}, status=403)
        reason = str(request.data.get('reason') or '').strip()
        if not reason:
            return Response({'reason': 'Explain why this presence record is being corrected.'}, status=400)
        presence = StudentDailyPresence.objects.select_for_update().select_related(
            'student__user', 'student__current_class__class_level', 'class_arm__class_level'
        ).filter(pk=pk, school=school).first()
        if not presence:
            return Response(status=404)
        before = _presence_payload(presence, school)
        for field in ('arrival_at', 'departure_at'):
            if field not in request.data:
                continue
            raw = request.data.get(field)
            if raw in (None, ''):
                setattr(presence, field, None)
                continue
            try:
                parsed = datetime.fromisoformat(str(raw))
                if timezone.is_naive(parsed):
                    parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            except (TypeError, ValueError):
                return Response({field: 'Use an ISO date-time.'}, status=400)
            setattr(presence, field, parsed)
        presence.correction_reason = reason[:300]
        try:
            presence.save()
        except DjangoValidationError as exc:
            return Response(getattr(exc, 'message_dict', {'detail': exc.messages}), status=400)
        from tenants.security import audit
        audit(request, 'attendance.student_presence_corrected', target=f'presence:{presence.pk}',
              details={'school_id': school.pk, 'student_id': presence.student_id,
                       'before': before, 'reason': presence.correction_reason})
        return Response(_presence_payload(presence, school))


class StudentPresenceSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = getattr(request, 'tenant', None)
        if not school or request.user.school_id != school.pk or request.user.role not in ('school_admin', 'principal', 'class_teacher'):
            return Response({'detail': 'School presence access required.'}, status=403)
        from enrollment.models import ClassArm
        classes = ClassArm.objects.filter(school=school).select_related('class_level')
        if request.user.role == 'class_teacher':
            classes = classes.filter(class_teacher=request.user)
        return Response({
            'arrival_cutoff_time': str(school.arrival_cutoff_time)[:5] if school.arrival_cutoff_time else None,
            'student_clockout_enabled': school.student_clockout_enabled,
            'classes': [{'id': arm.pk, 'name': arm.full_name} for arm in classes],
        })

    def patch(self, request):
        school = getattr(request, 'tenant', None)
        if not school or request.user.school_id != school.pk or request.user.role != 'school_admin':
            return Response({'detail': 'Only the school administrator can change presence settings.'}, status=403)
        enabled = request.data.get('student_clockout_enabled', school.student_clockout_enabled)
        if type(enabled) is not bool:
            return Response({'student_clockout_enabled': 'Use true or false.'}, status=400)
        raw_cutoff = request.data.get('arrival_cutoff_time')
        if raw_cutoff in (None, ''):
            cutoff = None
        else:
            try:
                cutoff = datetime.strptime(str(raw_cutoff), '%H:%M').time()
            except ValueError:
                return Response({'arrival_cutoff_time': 'Use HH:MM in 24-hour time.'}, status=400)
        school.student_clockout_enabled = enabled
        school.arrival_cutoff_time = cutoff
        school.save(update_fields=['student_clockout_enabled', 'arrival_cutoff_time'])
        from tenants.security import audit
        audit(request, 'attendance.presence_settings_changed', target=f'school:{school.pk}',
              details={'school_id': school.pk, 'clockout_enabled': enabled,
                       'arrival_cutoff_time': str(cutoff) if cutoff else None})
        return self.get(request)
