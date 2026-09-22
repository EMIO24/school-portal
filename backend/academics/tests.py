from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from tenants.models import School
from .models import AcademicSession, Holiday, Term


class HolidayAccessTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Calendar School', slug='calendar', subdomain='calendar')
        self.other = School.objects.create(name='Other School', slug='other-calendar', subdomain='other-calendar')
        self.admin = CustomUser.objects.create_user('admin@calendar.test', 'Password!123', school=self.school, role='school_admin')
        self.student = CustomUser.objects.create_user('student@calendar.test', 'Password!123', school=self.school, role='student')
        session = AcademicSession.objects.create(school=self.school, name='2026/27', start_date='2026-09-01', end_date='2027-07-31')
        other_session = AcademicSession.objects.create(school=self.other, name='2026/27', start_date='2026-09-01', end_date='2027-07-31')
        self.term = Term.objects.create(session=session, name='first', start_date='2026-09-01', end_date='2026-12-31')
        self.other_term = Term.objects.create(session=other_session, name='first', start_date='2026-09-01', end_date='2026-12-31')
        self.client = APIClient()
        self.headers = {'HTTP_X_SCHOOL_SLUG': 'calendar'}

    def test_admin_crud_persists_and_sessions_include_holidays(self):
        self.client.force_authenticate(self.admin)
        payload = {'term': self.term.pk, 'name': 'Christmas Break', 'start_date': '2026-12-20', 'end_date': '2026-12-31', 'holiday_type': 'public'}
        created = self.client.post('/api/holidays/', payload, format='json', **self.headers)
        self.assertEqual(created.status_code, 201, created.data)
        holiday_id = created.data['id']
        self.assertEqual(self.client.patch(f'/api/holidays/{holiday_id}/', {'name': 'Christmas Holiday'}, format='json', **self.headers).status_code, 200)
        sessions_response = self.client.get('/api/sessions/', **self.headers).data
        sessions = sessions_response.get('results', sessions_response)
        self.assertEqual(sessions[0]['terms'][0]['holidays'][0]['name'], 'Christmas Holiday')
        self.assertEqual(self.client.delete(f'/api/holidays/{holiday_id}/', **self.headers).status_code, 204)
        self.assertFalse(Holiday.objects.filter(pk=holiday_id).exists())

    def test_cross_school_and_non_admin_mutation_are_denied(self):
        self.client.force_authenticate(self.admin)
        payload = {'term': self.other_term.pk, 'name': 'Other', 'start_date': '2026-10-01', 'end_date': '2026-10-02', 'holiday_type': 'school'}
        self.assertEqual(self.client.post('/api/holidays/', payload, format='json', **self.headers).status_code, 403)
        holiday = Holiday.objects.create(term=self.term, name='Break', start_date='2026-10-01', end_date='2026-10-02')
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.patch(f'/api/holidays/{holiday.pk}/', {'name': 'Changed'}, format='json', **self.headers).status_code, 403)
