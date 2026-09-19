from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied


class PortalJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None
        user, token = result
        tenant = getattr(request, 'tenant', None)
        if tenant is not None and user.role != 'superadmin' and user.school_id != tenant.pk:
            raise PermissionDenied('Sign in to your own school.')
        allowed = ('/api/auth/me/', '/api/auth/change-password/', '/api/platform/me/', '/api/platform/password/')
        if user.must_change_password and request.path not in allowed:
            raise PermissionDenied('Change your temporary password before continuing.')
        return result

    def get_user(self, validated_token):
        from tenants.security import check_session
        user = super().get_user(validated_token)
        check_session(user, validated_token)
        return user


class PortalTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        from accounts.models import CustomUser
        from tenants.security import check_session
        token = RefreshToken(attrs['refresh'])
        user = CustomUser.objects.filter(pk=token['user_id'], is_active=True).first()
        if not user:
            raise AuthenticationFailed('Account is inactive.')
        check_session(user, token)
        from rest_framework_simplejwt.utils import get_md5_hash_password
        if token.get('hash_password') != get_md5_hash_password(user.password):
            raise AuthenticationFailed('Password changed. Sign in again.')
        return super().validate(attrs)
