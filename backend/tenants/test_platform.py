from django.test import TestCase
from django.core.cache import cache
from rest_framework.test import APIClient
from accounts.models import CustomUser
from .models import School, SchoolActivity


class PlatformTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = CustomUser.objects.create_superuser('owner@example.test', 'OwnerPass!2026', first_name='Owner', last_name='Test')
        self.school = School.objects.create(name='Existing', slug='existing', subdomain='existing')
        self.admin = CustomUser.objects.create_user('admin@example.test', 'AdminPass!2026', school=self.school, role='school_admin')
        self.client = APIClient()
        self.data = {'name': 'New School', 'subdomain': 'new-school', 'email': 'office@new.test',
            'administrator': {'email': 'admin@new.test', 'first_name': 'New', 'last_name': 'Admin', 'password': 'GoodPassword!2026'}}

    def test_every_management_endpoint_denies_non_owners(self):
        endpoints = [('/api/platform/me/', ['get']), ('/api/platform/schools/', ['get', 'post']),
                     (f'/api/platform/schools/{self.school.pk}/', ['get', 'post', 'patch']),
                     (f'/api/platform/schools/{self.school.pk}/administrators/', ['post', 'patch'])]
        for user in [None, self.admin]:
            self.client.force_authenticate(user)
            for url, methods in endpoints:
                for method in methods:
                    response = getattr(self.client, method)(url, {}, format='json')
                    self.assertIn(response.status_code, [401, 403], (url, method, response.data))
        self.assertEqual(School.objects.count(), 1)

    def test_public_registration_cannot_grant_owner_or_active_access(self):
        self.data.update(is_active=True, approval_status='approved', subscription_plan='premium')
        self.data['administrator'].update(role='superadmin', is_superuser=True)
        response = self.client.post('/api/platform/register/', self.data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        school = School.objects.get(subdomain='new-school')
        user = school.users.get()
        self.assertFalse(school.is_active)
        self.assertEqual(school.approval_status, 'pending')
        self.assertEqual(school.subscription_plan, 'free')
        self.assertEqual(user.role, 'school_admin')
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('GoodPassword!2026'))
        self.assertNotIn('password', str(response.data))
        response = self.client.post('/api/auth/login/', {'email': user.email, 'password': 'GoodPassword!2026'},
            format='json', HTTP_X_SCHOOL_SLUG='new-school')
        self.assertEqual(response.status_code, 401)
        self.client.force_authenticate(self.owner)
        response = self.client.post(f'/api/platform/schools/{school.pk}/', {'action': 'approve'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.client.force_authenticate(None)
        response = self.client.post('/api/auth/login/', {'email': user.email, 'password': 'GoodPassword!2026'},
            format='json', HTTP_X_SCHOOL_SLUG='new-school')
        self.assertEqual(response.status_code, 200, response.data)
        token = response.data['access']
        self.client.force_authenticate(self.owner)
        self.client.post(f'/api/platform/schools/{school.pk}/', {'action': 'suspend'}, format='json')
        self.client.force_authenticate(None)
        response = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION='Bearer ' + token, HTTP_X_SCHOOL_SLUG='new-school')
        self.assertEqual(response.status_code, 404)

    def test_create_update_usage_and_admin_scope(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/platform/schools/', self.data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        self.assertTrue(response.data['is_active'])
        response = self.client.patch(f'/api/platform/schools/{pk}/',
            {'subscription_plan': 'premium', 'subscription_ends_on': '2027-01-01', 'platform_notes': 'Manual renewal'}, format='json')
        self.assertEqual(response.data['subscription_plan'], 'premium')
        self.assertEqual(response.data['usage']['admin_count'], 1)
        response = self.client.patch(f'/api/platform/schools/{pk}/administrators/',
            {'id': self.admin.pk, 'is_active': False}, format='json')
        self.assertEqual(response.status_code, 404)
        admin = School.objects.get(pk=pk).users.get()
        response = self.client.patch(f'/api/platform/schools/{pk}/administrators/',
            {'id': admin.pk, 'is_active': False}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.get('/api/platform/schools/?search=New&plan=premium')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['summary']['schools'], 2)
        self.assertGreaterEqual(SchoolActivity.objects.filter(school_id=pk).count(), 2)

    def test_invalid_registration_is_atomic(self):
        self.data['administrator']['email'] = self.admin.email.upper()
        response = self.client.post('/api/platform/register/', self.data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(School.objects.count(), 1)
        self.data['administrator']['email'] = 'fresh@new.test'
        self.data['administrator']['password'] = '123'
        self.assertEqual(self.client.post('/api/platform/register/', self.data, format='json').status_code, 400)
        self.assertEqual(School.objects.count(), 1)

    def test_reject_and_transition_validation(self):
        self.client.post('/api/platform/register/', self.data, format='json')
        school = School.objects.get(subdomain='new-school')
        self.client.force_authenticate(self.owner)
        url = f'/api/platform/schools/{school.pk}/'
        self.assertEqual(self.client.post(url, {'action': 'activate'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'action': 'reject'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(url, {'action': 'approve'}, format='json').status_code, 400)
        school.refresh_from_db()
        self.assertFalse(school.is_active)


    def test_add_administrator_and_toggle_access(self):
        self.client.force_authenticate(self.owner)
        url = f'/api/platform/schools/{self.school.pk}/administrators/'
        response = self.client.post(url, self.data['administrator'], format='json')
        self.assertEqual(response.status_code, 201, response.data)
        new_admin = CustomUser.objects.get(email='admin@new.test')
        self.assertEqual(new_admin.school, self.school)
        self.assertEqual(new_admin.role, 'school_admin')
        self.assertTrue(new_admin.must_change_password)
        self.assertFalse(new_admin.is_staff)
        response = self.client.patch(url, {'id': self.admin.pk, 'is_active': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertFalse(self.admin.is_active)
        self.assertEqual(self.client.patch(url, {'id': 'bad', 'is_active': True}, format='json').status_code, 400)

    def test_owner_profile_and_registration_throttle(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/platform/me/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['role'], 'superadmin')
        self.client.force_authenticate(None)
        for _ in range(5):
            self.assertEqual(self.client.post('/api/platform/register/', {}, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/platform/register/', {}, format='json').status_code, 429)
