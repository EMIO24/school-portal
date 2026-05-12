"""
accounts/views.py

Authentication views for the school portal.

All paths under /api/auth/ are exempt from TenantMiddleware
(configured in middleware.py) so login works before tenant resolves.
Tenant validation happens INSIDE LoginView instead.
"""

import logging
import random
import string

from django.core.cache import cache

logger = logging.getLogger(__name__)
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView  # re-exported below

from tenants.serializers import SchoolPublicSerializer

from .permissions import IsAuthenticatedTenantUser
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    UserProfileSerializer,
)


class LoginView(APIView):
    """
    POST /api/auth/login/

    Request body:
        { "email": "...", "password": "..." }

    Response (200):
        {
            "access":               "<JWT access token>",
            "refresh":              "<JWT refresh token>",
            "role":                 "student",
            "must_change_password": false,
            "user":                 { ...UserProfileSerializer fields },
            "theme":                { ...school theme }
        }

    The frontend should:
      1. Store access + refresh in memory / secure storage.
      2. If must_change_password == true → redirect to /change-password.
      3. Inject theme into CSS variables (ThemeProvider handles this).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        # Auth paths are exempt from TenantMiddleware, so resolve tenant here
        # from X-School-Slug header or subdomain before passing to serializer.
        if not getattr(request, "tenant", None):
            request.tenant = _resolve_tenant_from_request(request)

        serializer = LoginSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user   = serializer.validated_data["user"]
        tokens = serializer.get_tokens(user)

        # Build theme from the user's school (None for superadmin)
        theme = None
        if user.school:
            theme = SchoolPublicSerializer(user.school).data

        return Response(
            {
                **tokens,                                   # access + refresh
                "role":                 user.role,
                "must_change_password": user.must_change_password,
                "user":                 UserProfileSerializer(user).data,
                "theme":                theme,
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    GET /api/auth/me/

    Returns the profile of the currently authenticated user.
    Requires a valid JWT in the Authorization header.
    """

    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """
        PATCH /api/auth/me/

        Update editable profile fields (first_name, last_name,
        phone_number, profile_photo). Email and role are read-only.
        """
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/

    Request body:
        {
            "current_password": "...",
            "new_password": "...",
            "confirm_password": "..."
        }

    On success: clears must_change_password flag and returns 200.
    Frontend should redirect to the dashboard after this.
    """

    permission_classes = [IsAuthenticatedTenantUser]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Password changed successfully."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Re-export simplejwt's refresh view so it lives under /api/auth/
class TokenRefreshView(TokenRefreshView):
    """
    POST /api/auth/token/refresh/

    Standard simplejwt refresh — exchange a valid refresh token
    for a new access token.
    """
    pass


# ── Parent OTP login ───────────────────────────────────────────────────────

def _make_otp():
    return ''.join(random.choices(string.digits, k=6))


def _resolve_tenant_from_request(request):
    """
    Resolve the School tenant from X-School-Slug header or subdomain.
    Used by auth-exempt views that bypass TenantMiddleware.
    """
    from tenants.models import School
    slug = request.headers.get('X-School-Slug') or _extract_subdomain_from_host(request)
    if not slug:
        return None
    return School.objects.filter(subdomain=slug, is_active=True).first()


def _extract_subdomain_from_host(request):
    host  = request.get_host().lower().split(':')[0]
    parts = host.split('.')
    if len(parts) >= 3:
        return parts[0]
    if len(parts) == 2 and parts[1] in ('localhost', 'test'):
        return parts[0]
    return None


class ParentOTPRequestView(APIView):
    """
    POST /api/auth/parent/otp-request/
    body: { phone: "080xxxxxxxx" }

    Generates a 6-digit OTP, stores it in cache for 10 min,
    and sends via Termii SMS.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        phone  = request.data.get('phone', '').strip().replace(' ', '')
        school = _resolve_tenant_from_request(request)

        if not phone:
            return Response({'error': 'Phone number required.'}, status=400)

        otp      = _make_otp()
        cache_key = f'parent_otp:{phone}'
        cache.set(cache_key, otp, timeout=600)

        school_name = school.name if school else 'Your School'
        message     = f'Your {school_name} login code is {otp}. Valid for 10 minutes.'

        try:
            from notifications.services.termii import TermiiService
            sender_id = school.slug[:11] if school else 'SCHOOL'
            TermiiService().send_sms(phone, message, sender_id, school=school)
        except Exception:
            logger.exception("OTP SMS failed for phone %s school %s", phone, getattr(school, 'id', None))
            # still return success — don't leak whether the phone number exists

        return Response({'detail': 'OTP sent.'})


class ParentOTPVerifyView(APIView):
    """
    POST /api/auth/parent/otp-verify/
    body: { phone: "080xxxxxxxx", otp: "123456" }

    Returns JWT tokens on success.
    Creates a parent user account if one doesn't exist for this phone.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        from .models import CustomUser

        phone  = request.data.get('phone', '').strip().replace(' ', '')
        otp    = request.data.get('otp', '').strip()
        school = _resolve_tenant_from_request(request)

        if not phone or not otp:
            return Response({'error': 'Phone and OTP required.'}, status=400)

        cache_key  = f'parent_otp:{phone}'
        stored_otp = cache.get(cache_key)

        if not stored_otp or stored_otp != otp:
            return Response({'error': 'Invalid or expired OTP.'}, status=401)

        cache.delete(cache_key)

        # Namespace email by school slug so the same phone at two schools
        # doesn't collide on the unique email constraint.
        school_slug = school.slug if school else 'noschl'
        otp_email   = f'{phone}_{school_slug}@otp.schoolportal.ng'

        user = CustomUser.objects.filter(phone_number=phone, role='parent', school=school).first()
        if not user:
            # create_user(password=None) already stores an unusable password hash;
            # no extra set_unusable_password() / save() needed.
            user = CustomUser.objects.create_user(
                email=otp_email,
                password=None,
                role='parent',
                school=school,
                phone_number=phone,
            )

        refresh = RefreshToken.for_user(user)
        theme   = SchoolPublicSerializer(school).data if school else None

        return Response({
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'role':    user.role,
            'user':    UserProfileSerializer(user).data,
            'theme':   theme,
        })


# ── Parent data views ──────────────────────────────────────────────────────

class ParentChildrenView(APIView):
    """GET /api/parent/children/ — list linked students."""
    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request):
        from .models import ParentStudentLink
        from enrollment.serializers import StudentProfileSerializer

        links = ParentStudentLink.objects.filter(
            parent=request.user,
            school=request.tenant,
        ).select_related('student__user', 'student__current_class')

        data = []
        for link in links:
            s = link.student
            data.append({
                'student_id':   s.id,
                'name':         s.user.get_full_name(),
                'admission_no': s.admission_number,
                'class':        s.current_class.full_name if s.current_class else '',
                'relationship': link.relationship,
            })
        return Response(data)


class ParentStudentDashboardView(APIView):
    """
    GET /api/parent/dashboard/{student_id}/
    One-shot endpoint returning result summary, attendance, fees, timetable today.
    """
    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request, pk):
        from .models import ParentStudentLink
        from enrollment.models import StudentProfile
        from academics.models import Term
        from gradebook.models import ScoreEntry
        from attendance.models import AttendanceRecord
        from fees.models import FeeSchedule, FeePayment
        from timetable.models import TimetableEntry
        from results.models import ResultRemark
        from django.db.models import Avg, Sum, Count, Q
        from decimal import Decimal
        import datetime

        school = request.tenant

        # Verify link
        if not ParentStudentLink.objects.filter(parent=request.user, student_id=pk, school=school).exists():
            return Response({'error': 'Not authorised for this student.'}, status=403)

        try:
            student = StudentProfile.objects.select_related('user', 'current_class__class_level').get(pk=pk, school=school)
        except StudentProfile.DoesNotExist:
            return Response(status=404)

        term = Term.objects.filter(session__school=school, is_current=True).first()

        # ── Result summary ─────────────────────────────────────────────────
        result_summary = None
        if term:
            scores = ScoreEntry.objects.filter(student=student.user, term=term, school=school)
            avg    = scores.aggregate(a=Avg('total_score'))['a']
            remark = ResultRemark.objects.filter(student=student.user, term=term, school=school).first()
            result_summary = {
                'average':  round(float(avg), 1) if avg else None,
                'position': remark.computed_position if remark else None,
                'subjects': scores.count(),
            }

        # ── Attendance summary ─────────────────────────────────────────────
        attendance_summary = None
        if term:
            summary = AttendanceRecord.objects.summary(student.user.id, term.id)
            total   = (summary.get('present', 0) or 0) + (summary.get('absent', 0) or 0) + (summary.get('late', 0) or 0)
            present = (summary.get('present', 0) or 0) + (summary.get('late', 0) or 0)
            pct     = round(present / total * 100) if total else 0

            # Last 7 days dot data
            seven_days_ago = timezone.now().date() - datetime.timedelta(days=7)
            recent = (
                AttendanceRecord.objects
                .filter(student=student.user, attendance_session__term=term)
                .filter(attendance_session__date__gte=seven_days_ago)
                .values('attendance_session__date', 'status')
                .order_by('attendance_session__date')
            )
            attendance_summary = {
                'percentage': pct,
                'present':    present,
                'total':      total,
                'warning':    pct < 75,
                'last_7_days': [{'date': str(r['attendance_session__date']), 'status': r['status']} for r in recent],
            }

        # ── Fee status ─────────────────────────────────────────────────────
        fee_status = None
        if term and student.current_class:
            schedules = FeeSchedule.objects.filter(school=school, term=term, class_level=student.current_class.class_level)
            total     = schedules.aggregate(t=Sum('amount'))['t'] or Decimal('0')
            paid      = FeePayment.objects.filter(student=student, fee_schedule__in=schedules).aggregate(t=Sum('amount_paid'))['t'] or Decimal('0')
            fee_status = {
                'total':       float(total),
                'paid':        float(paid),
                'outstanding': float(max(total - paid, Decimal('0'))),
            }

        # ── Today's timetable ──────────────────────────────────────────────
        today_schedule = []
        if term and student.current_class:
            day_map = {0: 'MON', 1: 'TUE', 2: 'WED', 3: 'THU', 4: 'FRI'}
            today   = day_map.get(timezone.now().weekday())
            if today:
                entries = (
                    TimetableEntry.objects
                    .filter(school=school, class_arm=student.current_class, day_of_week=today, term=term)
                    .select_related('period', 'subject', 'teacher')
                    .order_by('period__start_time')
                )
                now = timezone.localtime().time()
                for e in entries:
                    today_schedule.append({
                        'subject':     e.subject.name,
                        'teacher':     e.teacher.get_full_name() if e.teacher else '',
                        'start_time':  str(e.period.start_time),
                        'end_time':    str(e.period.end_time),
                        'is_current':  e.period.start_time <= now <= e.period.end_time,
                    })

        # ── Recent notifications ───────────────────────────────────────────
        from notifications.models import NotificationLog
        recent_notifs = (
            NotificationLog.objects
            .filter(school=school, student=student, status='sent')
            .order_by('-sent_at')[:5]
            .values('channel', 'message_body', 'sent_at')
        )

        return Response({
            'student': {
                'id':   student.id,
                'name': student.user.get_full_name(),
                'class': student.current_class.full_name if student.current_class else '',
            },
            'result_summary':     result_summary,
            'attendance_summary': attendance_summary,
            'fee_status':         fee_status,
            'timetable_today':    today_schedule,
            'recent_notifications': list(recent_notifs),
        })