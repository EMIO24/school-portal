from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import CustomUser
from .models import DemoRequest, School


class DemoRequestTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.data = {'school_name':'Demo School', 'contact_name':'Ada Owner', 'email':'ada@example.test', 'phone':'08012345678', 'student_population':120, 'location':'Lagos', 'message':'Please show us the portal.'}
        self.owner = CustomUser.objects.create_superuser('owner@demo.test', 'Password!123')
        self.school_user = CustomUser.objects.create_user('admin@demo.test', 'Password!123', school=School.objects.create(name='Demo Tenant'), role='school_admin')

    def test_public_request_is_validated_and_saved(self):
        self.assertEqual(self.client.post('/api/demo-requests/', self.data, format='json').status_code, 201)
        self.assertEqual(DemoRequest.objects.count(), 1)
        invalid = dict(self.data, email='not-an-email', phone='123')
        self.assertEqual(self.client.post('/api/demo-requests/', invalid, format='json').status_code, 400)

    def test_only_platform_owner_can_list_requests(self):
        DemoRequest.objects.create(**self.data)
        self.client.force_authenticate(self.school_user)
        self.assertEqual(self.client.get('/api/platform/demo-requests/').status_code, 403)
        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/platform/demo-requests/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['school_name'], self.data['school_name'])
