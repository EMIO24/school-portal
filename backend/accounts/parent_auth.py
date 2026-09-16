"""Tenant-bound, rate-limited, one-use parent challenges. No plaintext OTP logs."""
import re
import secrets
from datetime import timedelta
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser, ParentLoginChallenge
from .serializers import UserProfileSerializer
from tenants.serializers import SchoolPublicSerializer

class OTPThrottle(AnonRateThrottle):
    rate = '5/min'

def phone_value(value):
    value = re.sub(r'[ +()-]', '', str(value))
    return value if re.fullmatch(r'[0-9]{10,15}', value) else None

def parent_for(school, phone):
    return CustomUser.objects.filter(school=school, role='parent', phone_number=phone, is_active=True).first()

class ParentOTPRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    def post(self, request):
        from .views import _resolve_tenant_from_request
        from notifications.services.termii import TermiiService
        school = _resolve_tenant_from_request(request)
        phone = phone_value(request.data.get('phone', ''))
        if not school or school.approval_status != 'approved' or not phone:
            return Response({'error': 'Select a valid school and enter a valid phone number.'}, status=400)
        reply = {'detail': 'If this phone is registered, a login code will be sent.'}
        if not parent_for(school, phone):
            return Response(reply, status=202)
        now = timezone.now()
        with transaction.atomic():
            challenge, _ = ParentLoginChallenge.objects.get_or_create(school=school, phone=phone, defaults={'requested_at': now-timedelta(minutes=2), 'expires_at':now})
            challenge = ParentLoginChallenge.objects.select_for_update().get(pk=challenge.pk)
            if challenge.requested_at > now-timedelta(seconds=60):
                return Response(reply, status=202)
            code = f'{secrets.randbelow(1000000):06d}'
            challenge.code_hash = make_password(code)
            challenge.expires_at, challenge.requested_at = now+timedelta(minutes=5), now
            challenge.attempts, challenge.consumed = 0, False
            challenge.save()
        ok, _ = TermiiService().send_sms(phone, f'Your {school.name} login code is {code}. Valid for 5 minutes.', school.slug[:11], school=school, sensitive=True)
        if not ok:
            ParentLoginChallenge.objects.filter(pk=challenge.pk, requested_at=now).update(consumed=True)
            return Response({'error': 'SMS service unavailable. Please try again later.'}, status=503)
        return Response(reply, status=202)

class ParentOTPVerifyView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OTPThrottle]

    @transaction.atomic
    def post(self, request):
        from .views import _resolve_tenant_from_request
        school = _resolve_tenant_from_request(request)
        phone, code = phone_value(request.data.get('phone','')), str(request.data.get('otp','')).strip()
        error = Response({'error': 'Invalid or expired code.'}, status=401)
        if not school or not phone or not re.fullmatch(r'[0-9]{6}', code): return error
        row = ParentLoginChallenge.objects.select_for_update().filter(school=school, phone=phone).first()
        if not row or row.consumed or row.attempts >= 5 or row.expires_at <= timezone.now(): return error
        row.attempts += 1
        valid = check_password(code, row.code_hash)
        user = parent_for(school, phone)
        row.consumed = bool(valid or row.attempts >= 5)
        row.save(update_fields=['attempts','consumed'])
        if not valid or not user: return error
        refresh = RefreshToken.for_user(user)
        return Response({'access':str(refresh.access_token),'refresh':str(refresh),'role':user.role,'user':UserProfileSerializer(user).data,'theme':SchoolPublicSerializer(school).data})
