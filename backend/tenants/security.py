"""Platform MFA, replay prevention, session revocation and audit recording."""
import base64
import hashlib
import hmac
import io
import ipaddress
import secrets
import time
from datetime import timedelta
import pyotp
import qrcode
from cryptography.fernet import Fernet
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from .models import PlatformSecurity, PlatformEvent


def cipher():
    key = getattr(settings, 'PLATFORM_MFA_KEY', '')
    if not key:
        raise AuthenticationFailed('Platform MFA is not configured. Contact support.')
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        raise


def audit(request, action, target='', details=None, actor=None):
    actor = actor or (request.user if request and request.user.is_authenticated else None)
    raw_ip = request.META.get('REMOTE_ADDR') if request else None
    try:
        ip = str(ipaddress.ip_address(raw_ip))
    except ValueError:
        ip = None
    PlatformEvent.objects.create(actor=actor, actor_email=actor.email if actor else '',
        action=action, target=str(target), details=details or {}, ip_address=ip)


def check_session(user, token):
    if user.role != 'superadmin':
        return
    state = PlatformSecurity.objects.filter(user=user, enabled=True).first()
    if not state or not token.get('mfa') or token.get('mfa_version') != state.session_version:
        raise AuthenticationFailed('Sign in again and complete two-factor authentication.')


def start_challenge(user, request):
    try:
        with transaction.atomic():
            state, _ = PlatformSecurity.objects.get_or_create(user=user)
            state = PlatformSecurity.objects.select_for_update().get(pk=state.pk)
            if state.locked_until and state.locked_until > timezone.now():
                raise PermissionDenied('Too many failed codes. Try again in 15 minutes.')
            if state.locked_until:
                state.failures = 0
                state.locked_until = None
            nonce = secrets.token_hex(24)
            state.challenge_nonce = hashlib.sha256(nonce.encode()).hexdigest()
            result = {'mfa_required': True, 'mfa_setup_required': not state.enabled,
                      'challenge': signing.dumps({'uid': user.pk, 'nonce': nonce, 'version': state.session_version}, salt='platform-mfa')}
            if not state.enabled:
                # Retrying a password sign-in must not invalidate the authenticator
                # the user has already scanned while enrollment is still pending.
                if state.encrypted_secret:
                    secret = cipher().decrypt(state.encrypted_secret.encode()).decode()
                else:
                    secret = pyotp.random_base32()
                    state.encrypted_secret = cipher().encrypt(secret.encode()).decode()
                uri = pyotp.TOTP(secret).provisioning_uri(user.email, issuer_name='School Portal Platform')
                output = io.BytesIO()
                qrcode.make(uri).save(output, format='PNG')
                result.update(secret=secret, qr_code='data:image/png;base64,' + base64.b64encode(output.getvalue()).decode())
            state.save()
            audit(request, 'mfa.challenge', actor=user)
        response = Response(result, status=202)
        response['Cache-Control'] = 'no-store'
        return response
    except Exception:
        raise


def consume_code(state, code):
    code = str(code).strip()
    compact = ''.join(code.split())
    if len(compact) == 6 and compact.isascii() and compact.isdigit():
        code = compact
        totp = pyotp.TOTP(cipher().decrypt(state.encrypted_secret.encode()).decode())
        step = int(time.time()) // 30
        for candidate in [step - 1, step, step + 1]:
            if candidate > state.last_step and hmac.compare_digest(totp.at(candidate * 30), code):
                state.last_step = candidate
                return True
    elif state.enabled:
        digest = hashlib.sha256(code.encode()).hexdigest()
        for stored in state.recovery_hashes:
            if hmac.compare_digest(stored, digest):
                state.recovery_hashes = [v for v in state.recovery_hashes if v != stored]
                return True
    return False


class MFAThrottle(AnonRateThrottle):
    rate = '30/hour'


class VerifyMFA(APIView):
    def get_authenticate_header(self, request):
        return 'MFA'

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [MFAThrottle]

    def post(self, request):
        from accounts.models import CustomUser
        from accounts.serializers import LoginSerializer, UserProfileSerializer
        try:
            payload = signing.loads(request.data.get('challenge', ''), salt='platform-mfa', max_age=300)
        except (signing.BadSignature, TypeError):
            raise AuthenticationFailed('This sign-in expired. Enter your password again.')
        code = request.data.get('code', '')
        valid = False
        recovery = []
        with transaction.atomic():
            state = PlatformSecurity.objects.select_for_update().filter(user_id=payload['uid']).first()
            user = CustomUser.objects.filter(pk=payload['uid'], role='superadmin', is_active=True).first()
            if not state or not user or state.session_version != payload['version'] or not hmac.compare_digest(
                state.challenge_nonce, hashlib.sha256(payload['nonce'].encode()).hexdigest()):
                raise AuthenticationFailed('This sign-in expired. Enter your password again.')
            if state.locked_until and state.locked_until > timezone.now():
                raise PermissionDenied('Too many failed codes. Try again in 15 minutes.')
            valid = consume_code(state, code)
            if valid:
                if not state.enabled:
                    recovery = [secrets.token_hex(10) for _ in range(8)]
                    state.recovery_hashes = [hashlib.sha256(v.encode()).hexdigest() for v in recovery]
                    state.enabled = True
                    audit(request, 'mfa.enrolled', actor=user)
                state.failures = 0
                state.locked_until = None
                state.challenge_nonce = ''
                audit(request, 'platform.login', actor=user)
            else:
                state.failures += 1
                if state.failures >= 5:
                    state.locked_until = timezone.now() + timedelta(minutes=15)
                    state.challenge_nonce = ''
                audit(request, 'mfa.failed', actor=user)
            state.save()
        if not valid:
            raise AuthenticationFailed('Invalid or already used code. Try the next authenticator code or a recovery code.')
        tokens = LoginSerializer().get_tokens(user, mfa_version=state.session_version)
        response = Response({**tokens, 'user': UserProfileSerializer(user).data, 'role': user.role,
            'must_change_password': user.must_change_password, 'theme': None, 'recovery_codes': recovery})
        response['Cache-Control'] = 'no-store'
        return response
