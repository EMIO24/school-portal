import hashlib
import time
from unittest.mock import patch
import pyotp
from django.core.cache import cache
from django.test import TestCase, RequestFactory
from rest_framework.test import APIClient
from accounts.models import CustomUser
from accounts.serializers import LoginSerializer
from .models import PlatformSecurity, PlatformEvent, School
from .security import cipher

class PlatformSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = CustomUser.objects.create_superuser('owner@platform.test', 'OwnerStrong!2026', first_name='Owner', last_name='Test')
        self.client = APIClient()

    def challenge(self):
        result = self.client.post('/api/auth/login/', {'email': self.owner.email, 'password': 'OwnerStrong!2026'}, format='json', HTTP_X_SCHOOL_SLUG='absent-school')
        self.assertEqual(result.status_code, 202, result.data)
        self.assertNotIn('access', result.data)
        return result.data

    def enroll(self):
        challenge = self.challenge()
        response = self.client.post('/api/platform/auth/verify/', {'challenge': challenge['challenge'], 'code': pyotp.TOTP(challenge['secret']).now()}, format='json', HTTP_X_SCHOOL_SLUG='absent-school')
        self.assertEqual(response.status_code, 200, response.data)
        return challenge, response.data

    def test_enroll_without_schools_replay_recovery_and_old_tokens(self):
        legacy = LoginSerializer().get_tokens(self.owner)
        challenge, login = self.enroll()
        state = PlatformSecurity.objects.get(user=self.owner)
        self.assertTrue(state.enabled)
        self.assertNotIn(challenge['secret'], state.encrypted_secret)
        self.assertEqual(len(login['recovery_codes']), 8)
        self.assertNotIn(login['recovery_codes'][0], str(state.recovery_hashes))
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + legacy['access'])
        self.assertEqual(self.client.get('/api/platform/schools/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/token/refresh/', {'refresh': legacy['refresh']}, format='json').status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + login['access'])
        self.assertEqual(self.client.get('/api/platform/schools/', HTTP_X_SCHOOL_SLUG='absent-school').status_code, 200)
        self.client.credentials()
        replay = self.client.post('/api/platform/auth/verify/', {'challenge': challenge['challenge'], 'code': pyotp.TOTP(challenge['secret']).now()}, format='json')
        self.assertEqual(replay.status_code, 401)
        fresh = self.challenge()
        self.assertNotIn('secret', fresh)
        recovery = login['recovery_codes'][0]
        result = self.client.post('/api/platform/auth/verify/', {'challenge': fresh['challenge'], 'code': recovery}, format='json')
        self.assertEqual(result.status_code, 200)
        fresh = self.challenge()
        self.assertEqual(self.client.post('/api/platform/auth/verify/', {'challenge': fresh['challenge'], 'code': recovery}, format='json').status_code, 401)
        events = str(list(PlatformEvent.objects.values('details')))
        self.assertNotIn(challenge['secret'], events)
        self.assertNotIn(recovery, events)

    def test_bad_codes_lock_account_across_new_password_challenges(self):
        challenge = self.challenge()
        for _ in range(5):
            response = self.client.post('/api/platform/auth/verify/', {'challenge': challenge['challenge'], 'code': 'invalid'}, format='json')
            self.assertEqual(response.status_code, 401)
        response = self.client.post('/api/auth/login/', {'email': self.owner.email, 'password': 'OwnerStrong!2026'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PlatformSecurity.objects.get(user=self.owner).enabled)

    def test_expired_challenge_and_totp_reuse_are_rejected(self):
        challenge, login = self.enroll()
        with patch('django.core.signing.time.time', return_value=time.time() + 301):
            self.assertEqual(self.client.post('/api/platform/auth/verify/', {'challenge': challenge['challenge'], 'code': '123456'}, format='json').status_code, 401)
        fresh = self.challenge()
        self.assertEqual(self.client.post('/api/platform/auth/verify/', {'challenge': fresh['challenge'], 'code': pyotp.TOTP(challenge['secret']).now()}, format='json').status_code, 401)

    def test_viewer_denied_management_and_account_disable_revokes_sessions(self):
        _, login = self.enroll()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + login['access'])
        result = self.client.post('/api/platform/accounts/', {'email': 'viewer@platform.test', 'first_name': 'Read', 'last_name': 'Only', 'password': 'ViewerStrong!2026', 'access_level': 'viewer'}, format='json')
        self.assertEqual(result.status_code, 201, result.data)
        viewer = CustomUser.objects.get(email='viewer@platform.test')
        self.assertFalse(viewer.is_staff)
        self.assertFalse(viewer.is_superuser)
        viewer.must_change_password = False
        viewer.save(update_fields=['must_change_password'])
        state = viewer.platform_security
        state.enabled = True
        state.encrypted_secret = cipher().encrypt(pyotp.random_base32().encode()).decode()
        state.save()
        tokens = LoginSerializer().get_tokens(viewer, mfa_version=state.session_version)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + tokens['access'])
        self.assertEqual(self.client.get('/api/platform/schools/').status_code, 200)
        for url in ['/api/platform/accounts/', '/api/platform/audit/', '/api/schools/']:
            self.assertEqual(self.client.post(url, {}, format='json').status_code, 403)
        self.assertEqual(self.client.post('/api/platform/schools/', {}, format='json').status_code, 403)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + login['access'])
        self.assertEqual(self.client.patch('/api/platform/accounts/', {'id': viewer.pk, 'is_active': False}, format='json').status_code, 200)
        self.assertEqual(self.client.patch('/api/platform/accounts/', {'id': viewer.pk, 'is_active': True}, format='json').status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + tokens['access'])
        self.assertEqual(self.client.get('/api/platform/schools/').status_code, 401)
        self.client.credentials()
        self.assertEqual(self.client.post('/api/auth/token/refresh/', {'refresh': tokens['refresh']}, format='json').status_code, 401)

    def test_suspended_context_and_detailed_changes(self):
        school = School.objects.create(name='Stopped', subdomain='stopped', slug='stopped', is_active=False)
        _, login = self.enroll()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + login['access'])
        response = self.client.patch(f'/api/platform/schools/{school.pk}/', {'subscription_plan': 'premium'}, format='json', HTTP_X_SCHOOL_SLUG='stopped', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(response.status_code, 200, response.data)
        event = PlatformEvent.objects.get(action='school.updated')
        self.assertEqual(event.details['subscription_plan'], {'before': 'free', 'after': 'premium'})
        self.assertEqual(event.actor_email, self.owner.email)
        self.assertEqual(event.ip_address, '127.0.0.1')
        self.assertEqual(self.client.get('/api/students/', HTTP_X_SCHOOL_SLUG='stopped').status_code, 404)

    def test_school_isolation_read_write_and_header_spoof(self):
        from enrollment.models import ClassLevel
        a = School.objects.create(name='A', slug='school-a', subdomain='school-a')
        b = School.objects.create(name='B', slug='school-b', subdomain='school-b')
        level = ClassLevel.objects.create(school=b, name='JSS1', order_index=0)
        admin = CustomUser.objects.create_user('admin@a.test', 'PasswordStrong!2026', role='school_admin', school=a, must_change_password=False)
        token = LoginSerializer().get_tokens(admin)['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        url = f'/api/class-levels/{level.pk}/'
        self.assertIn(self.client.get(url, HTTP_X_SCHOOL_SLUG='school-a').status_code, (403,404))
        self.assertEqual(self.client.patch(url, {'name': 'JSS2'}, format='json', HTTP_X_SCHOOL_SLUG='school-a').status_code, 404)
        self.assertEqual(self.client.get(url, HTTP_X_SCHOOL_SLUG='school-b').status_code, 403)
        self.assertEqual(self.client.delete(url, HTTP_X_SCHOOL_SLUG='school-a').status_code, 404)
        for method in ['get', 'post', 'patch']:
            self.assertEqual(getattr(self.client, method)('/api/platform/schools/', {}, format='json', HTTP_X_SCHOOL_SLUG='absent').status_code, 403)
        level.refresh_from_db()
        self.assertEqual(level.name, 'JSS1')

    def test_django_admin_requires_mfa_and_no_legacy_session(self):
        from django.test import Client
        client = Client()
        client.force_login(self.owner)
        self.assertEqual(client.get('/superadmin/').status_code, 302)
        client.logout()
        result = client.post('/superadmin/login/?next=/superadmin/', {'username': self.owner.email, 'password': 'OwnerStrong!2026', 'verification_code': '123456'})
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, 'Set up two-factor')
        _, login = self.enroll()
        result = client.post('/superadmin/login/?next=/superadmin/', {'username': self.owner.email, 'password': 'OwnerStrong!2026', 'verification_code': login['recovery_codes'][0]})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(client.get('/superadmin/').status_code, 200)


    def test_retry_keeps_scanned_setup_key_and_accepts_grouped_code(self):
        first = self.challenge()
        second = self.challenge()
        self.assertEqual(first['secret'], second['secret'])
        self.assertNotEqual(first['challenge'], second['challenge'])
        code = pyotp.TOTP(first['secret']).now()
        response = self.client.post('/api/platform/auth/verify/', {
            'challenge': second['challenge'], 'code': code[:3] + ' ' + code[3:]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(PlatformSecurity.objects.get(user=self.owner).enabled)

    def test_non_ascii_digits_are_rejected_without_server_error(self):
        challenge = self.challenge()
        response = self.client.post('/api/platform/auth/verify/', {
            'challenge': challenge['challenge'], 'code': chr(0x0661) * 6}, format='json')
        self.assertEqual(response.status_code, 401)
