from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.db import transaction
from tenants.models import PlatformSecurity
from tenants.security import consume_code, audit


class MFAAdminAuthenticationForm(AdminAuthenticationForm):
    verification_code = forms.CharField(label='Authenticator or recovery code', max_length=32)

    def clean(self):
        cleaned = super().clean()
        user = self.get_user()
        if not user or user.role != 'superadmin':
            raise forms.ValidationError('Use a platform owner account.')
        with transaction.atomic():
            state = PlatformSecurity.objects.select_for_update().filter(user=user, enabled=True, access_level='owner').first()
            if not state:
                raise forms.ValidationError('Set up two-factor authentication through the platform login first.')
            from django.utils import timezone
            from datetime import timedelta
            if state.locked_until and state.locked_until > timezone.now():
                raise forms.ValidationError('Too many attempts. Try again in 15 minutes.')
            valid = consume_code(state, cleaned.get('verification_code', ''))
            if valid:
                state.failures = 0
                state.locked_until = None
                audit(self.request, 'platform.admin_login', actor=user)
                self.request.session['platform_mfa_version'] = state.session_version
            else:
                state.failures += 1
                if state.failures >= 5:
                    state.locked_until = timezone.now() + timedelta(minutes=15)
            state.save()
        if not valid:
            raise forms.ValidationError('Invalid or already used verification code.')
        return cleaned


def admin_permission(request):
    user = request.user
    if not (user.is_authenticated and user.is_active and user.is_staff and user.role == 'superadmin'):
        return False
    state = getattr(user, 'platform_security', None)
    return bool(state and state.enabled and state.access_level == 'owner' and
                request.session.get('platform_mfa_version') == state.session_version)
