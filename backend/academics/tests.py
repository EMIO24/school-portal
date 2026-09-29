from django.test import TestCase
from unittest.mock import patch
from datetime import date
from rest_framework.test import APIClient

from accounts.models import CustomUser
from tenants.models import School
from tenants.models import PlatformEvent
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

    def test_holiday_range_partial_update_and_foreign_term_are_rejected(self):
        self.client.force_authenticate(self.admin)
        base = {'term': self.term.pk, 'name': 'Half term', 'start_date': '2026-10-10', 'end_date': '2026-10-12', 'holiday_type': 'school'}
        for change in ({'end_date': '2026-10-09'}, {'start_date': '2026-08-31'}, {'end_date': '2027-01-01'}):
            self.assertEqual(self.client.post('/api/holidays/', {**base, **change}, format='json', **self.headers).status_code, 400)
        created = self.client.post('/api/holidays/', base, format='json', **self.headers)
        self.assertEqual(created.status_code, 201)
        url = f"/api/holidays/{created.data['id']}/"
        self.assertEqual(self.client.patch(url, {'end_date': '2026-10-09'}, format='json', **self.headers).status_code, 400)
        self.assertEqual(self.client.patch(url, {'term': self.other_term.pk}, format='json', **self.headers).status_code, 403)
        self.assertEqual(Holiday.objects.get(pk=created.data['id']).term_id, self.term.pk)

    @patch('academics.views.timezone.localdate', return_value=date(2026, 10, 11))
    def test_started_holiday_retains_history_and_audit(self, _today):
        self.client.force_authenticate(self.admin)
        created = self.client.post('/api/holidays/', {'term': self.term.pk, 'name': 'Break',
            'start_date': '2026-10-10', 'end_date': '2026-10-12', 'holiday_type': 'school'}, format='json', **self.headers)
        url = f"/api/holidays/{created.data['id']}/"
        self.assertEqual(self.client.patch(url, {'name': 'Changed'}, format='json', **self.headers).status_code, 400)
        self.assertEqual(self.client.delete(url, **self.headers).status_code, 400)
        self.assertEqual(Holiday.objects.get(pk=created.data['id']).name, 'Break')
        self.assertEqual(PlatformEvent.objects.filter(action='calendar.holiday_created').count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action='calendar.holiday_changed').count(), 0)

    @patch('academics.views.timezone.localdate', return_value=date(2026, 9, 27))
    def test_future_holiday_correction_and_delete_are_audited_once(self, _today):
        self.client.force_authenticate(self.admin)
        created = self.client.post('/api/holidays/', {'term': self.term.pk, 'name': 'Break',
            'start_date': '2026-10-10', 'end_date': '2026-10-12'}, format='json', **self.headers)
        url = f"/api/holidays/{created.data['id']}/"
        self.assertEqual(self.client.patch(url, {'name': 'School Break'}, format='json', **self.headers).status_code, 200)
        self.assertEqual(self.client.patch(url, {'name': 'School Break'}, format='json', **self.headers).status_code, 200)
        self.assertEqual(PlatformEvent.objects.filter(action='calendar.holiday_changed').count(), 1)
        self.assertEqual(self.client.delete(url, **self.headers).status_code, 204)
        self.assertEqual(PlatformEvent.objects.filter(action='calendar.holiday_deleted').count(), 1)
