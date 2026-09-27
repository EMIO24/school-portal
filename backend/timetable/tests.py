from datetime import date, time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from unittest import skipUnless
from rest_framework.test import APIClient

from accounts.models import CustomUser
from academics.models import AcademicSession, Holiday, Term
from enrollment import test_operations as operations
from enrollment.models import ClassArm, ClassLevel, StaffProfile, Subject
from tenants.models import PlatformEvent, School
from .models import LessonRecord, Period, TimetableEntry


class TeachingOperationsTests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)
    day = date(2026, 9, 21)  # Monday in the fixture term

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)
        self.period = Period.objects.create(school=self.school, name='Period 1', start_time=time(8), end_time=time(9), order_index=1)
        self.slot = TimetableEntry.objects.create(school=self.school, term=self.term, class_arm=self.arm,
            subject=self.subject, teacher=self.teacher, day_of_week='MON', period=self.period)
        self.url = f'/api/timetable/lessons/{self.slot.pk}/{self.day}/'
        self.daily = f'/api/timetable/lessons/?date={self.day}'

    def save(self, outcome='delivered', revision=0, **extra):
        return self.client.put(self.url, {'outcome': outcome, 'revision': revision, **extra}, format='json')

    def test_unresolved_is_not_missed_and_only_real_school_day_is_derived(self):
        self.assertIsNone(self.client.get(self.daily).data['lessons'][0]['outcome'])
        self.assertEqual(LessonRecord.objects.count(), 0)
        Holiday.objects.create(term=self.term, name='School closed', start_date=self.day, end_date=self.day)
        self.assertEqual(self.client.get(self.daily).data['lessons'], [])
        self.assertEqual(self.save('missed').status_code, 400)
        self.assertEqual(self.client.get('/api/timetable/lessons/?date=2026-09-20').data['lessons'], [])

    @patch('timetable.teaching.timezone.localdate', return_value=day)
    def test_teacher_delivered_retry_correction_and_audit(self, _today):
        self.client.force_authenticate(self.teacher)
        first = self.save()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data['scheduled_teacher'], self.teacher.pk)
        self.assertEqual(first.data['actual_teacher'], self.teacher.pk)
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(LessonRecord.objects.count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action__startswith='lesson.').count(), 1)
        changed = self.save('missed', revision=1, note='Class unavailable')
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(changed.data['revision'], 2)
        self.assertEqual(changed.data['actual_teacher'], None)
        self.assertEqual(self.save('cancelled', revision=2).status_code, 403)
        self.assertEqual(self.save('delivered', revision=1).status_code, 409)
        self.assertEqual(PlatformEvent.objects.filter(action__startswith='lesson.').count(), 2)

    def test_admin_cancel_substitute_and_foreign_substitute_denied(self):
        substitute = CustomUser.objects.create_user(email='sub@operations.test', password='Test-password-26!',
            role='teacher', school=self.school, must_change_password=False)
        StaffProfile.objects.create(school=self.school, user=substitute)
        foreign = CustomUser.objects.create_user(email='foreign@operations.test', password='Test-password-26!',
            role='teacher', school=self.other, must_change_password=False)
        StaffProfile.objects.create(school=self.other, user=foreign)
        self.assertEqual(self.save('substituted', actual_teacher=foreign.pk).status_code, 400)
        first = self.save('substituted', actual_teacher=substitute.pk)
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(first.data['scheduled_teacher'], self.teacher.pk)
        self.assertEqual(first.data['actual_teacher'], substitute.pk)
        cancelled = self.save('cancelled', revision=1, note='School activity')
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        self.assertEqual(cancelled.data['actual_teacher'], None)
        self.assertEqual(self.client.get(self.daily + '&outcome=cancelled').data['lessons'][0]['outcome'], 'cancelled')

    def test_history_survives_slot_edit_and_delete(self):
        self.save()
        old = self.client.get(self.daily).data['lessons'][0]
        self.slot.subject.name = 'Renamed subject'
        self.slot.subject.save()
        self.slot.day_of_week = 'TUE'
        self.slot.save()
        self.assertEqual(self.client.get(self.daily).data['lessons'][0]['subject_name'], old['subject_name'])
        self.slot.delete()
        self.assertEqual(self.client.get(self.daily).data['lessons'][0]['slot_id'], old['slot_id'])
        self.assertEqual(self.save('missed', revision=1).status_code, 200)

    @patch('timetable.teaching.timezone.localdate', return_value=day)
    def test_teacher_and_other_roles_cannot_fabricate_outcomes(self, _today):
        unrelated = CustomUser.objects.create_user(email='unrelated@operations.test', password='Test-password-26!',
            role='teacher', school=self.school, must_change_password=False)
        StaffProfile.objects.create(school=self.school, user=unrelated)
        parent = CustomUser.objects.create_user(email='parent-teaching@operations.test', password='Test-password-26!',
            role='parent', school=self.school, must_change_password=False)
        for actor in (unrelated, self.student, parent):
            self.client.force_authenticate(actor)
            self.assertEqual(self.save().status_code, 403)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(self.daily).data['lessons'][0]['slot_id'], self.slot.pk)
        self.assertEqual(self.client.put(f'/api/timetable/lessons/99999/{self.day}/',
            {'outcome': 'delivered', 'revision': 0}, format='json').status_code, 404)
        self.assertEqual(self.save('invalid').status_code, 400)
        self.assertEqual(LessonRecord.objects.count(), 0)

    def test_foreign_slot_and_teacher_read_isolation(self):
        other_admin = CustomUser.objects.create_user(email='otheradmin@operations.test', password='Test-password-26!',
            role='school_admin', school=self.other, must_change_password=False)
        self.client.force_authenticate(other_admin)
        self.assertEqual(self.client.get(self.daily).status_code, 403)
        self.assertEqual(self.save().status_code, 403)
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.other.slug)
        self.client.force_authenticate(other_admin)
        self.assertEqual(self.client.get(self.daily).data['lessons'], [])
        self.assertEqual(self.save().status_code, 404)
        foreign_teacher = CustomUser.objects.create_user(email='otherteacher@operations.test', password='Test-password-26!',
            role='teacher', school=self.other, must_change_password=False)
        StaffProfile.objects.create(school=self.other, user=foreign_teacher)
        self.client.force_authenticate(foreign_teacher)
        self.assertEqual(self.client.get(self.daily).data['lessons'], [])
        self.assertEqual(self.save().status_code, 404)

    def test_term_date_and_future_boundaries(self):
        self.assertEqual(self.client.put(f'/api/timetable/lessons/{self.slot.pk}/2026-08-31/',
            {'outcome': 'delivered', 'revision': 0}, format='json').status_code, 400)
        self.assertEqual(self.client.put(f'/api/timetable/lessons/{self.slot.pk}/2026-09-22/',
            {'outcome': 'delivered', 'revision': 0}, format='json').status_code, 400)
        with patch('timetable.teaching.timezone.localdate', return_value=date(2026, 9, 20)):
            self.assertEqual(self.save().status_code, 400)

    def test_recorded_old_term_remains_readable_after_term_switch(self):
        self.assertEqual(self.save('missed').status_code, 201)
        next_term = Term.objects.create(session=self.session, name='second',
            start_date=date(2027, 1, 1), end_date=date(2027, 4, 1), is_current=True)
        self.assertTrue(next_term.is_current)
        response = self.client.get(self.daily)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lessons'][0]['outcome'], 'missed')

    @patch('timetable.teaching.timezone.localdate', return_value=day)
    def test_admin_correction_after_teacher_and_inactive_substitute(self, _today):
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.save().status_code, 201)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.save('missed', revision=1).status_code, 200)
        self.assertEqual(LessonRecord.objects.get().recorded_by_id, self.teacher.pk)
        self.assertEqual(PlatformEvent.objects.filter(action='lesson.outcome_corrected').count(), 1)
        self.teacher.staff_profile.employment_status = 'suspended'
        self.teacher.staff_profile.save()
        self.assertEqual(self.save('substituted', revision=2, actual_teacher=self.teacher.pk).status_code, 400)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.save('delivered', revision=2).status_code, 403)

    def test_school_id_cannot_override_tenant_and_unrelated_teacher_cannot_read(self):
        self.assertEqual(self.client.put(self.url, {'school': self.other.pk,
            'outcome': 'delivered', 'revision': 0}, format='json').status_code, 201)
        self.assertEqual(LessonRecord.objects.get().school_id, self.school.pk)
        unrelated = CustomUser.objects.create_user(email='unrelated2@operations.test', password='Test-password-26!',
            role='teacher', school=self.school, must_change_password=False)
        StaffProfile.objects.create(school=self.school, user=unrelated)
        self.client.force_authenticate(unrelated)
        self.assertEqual(self.client.get(self.daily).data['lessons'], [])
        self.assertEqual(self.save('missed', revision=1).status_code, 403)

    def test_daily_list_query_count_does_not_grow_per_slot(self):
        with CaptureQueriesContext(connection) as one:
            self.assertEqual(len(self.client.get(self.daily).data['lessons']), 1)
        for number in range(20):
            arm = ClassArm.objects.create(school=self.school, class_level=self.level, name=f'Q{number}')
            TimetableEntry.objects.create(school=self.school, term=self.term, class_arm=arm,
                subject=self.subject, day_of_week='MON', period=self.period)
        with CaptureQueriesContext(connection) as many:
            self.assertEqual(len(self.client.get(self.daily).data['lessons']), 21)
        print(f'TEACHING_DAILY_QUERY_COUNTS slots=1:{len(one)} slots=21:{len(many)}')
        self.assertLessEqual(len(many) - len(one), 2)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL concurrency check')
class TeachingPostgresRaceTests(TransactionTestCase):
    def test_simultaneous_first_save_creates_one_outcome_and_one_audit(self):
        school = School.objects.create(name='Race School', slug='race-school', subdomain='race-school', subscription_plan='basic')
        admin = CustomUser.objects.create_user(email='race-admin@operations.test', password='Test-password-26!',
            role='school_admin', school=school, must_change_password=False)
        session = AcademicSession.objects.create(school=school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 30))
        term = Term.objects.create(session=session, name='first',
            start_date=date(2026, 9, 1), end_date=date(2026, 12, 18))
        level = ClassLevel.objects.create(school=school, name='JSS1')
        arm = ClassArm.objects.create(school=school, class_level=level, name='A')
        subject = Subject.objects.create(school=school, name='Math', code='MATH')
        period = Period.objects.create(school=school, name='Period 1', start_time=time(8), end_time=time(9), order_index=1)
        slot = TimetableEntry.objects.create(school=school, term=term, class_arm=arm, subject=subject,
            day_of_week='MON', period=period)
        url = f'/api/timetable/lessons/{slot.pk}/2026-09-21/'
        original_create = LessonRecord.objects.create
        barrier = Barrier(2)

        def racing_create(**kwargs):
            barrier.wait(timeout=10)
            return original_create(**kwargs)

        def save():
            close_old_connections()
            client = APIClient(HTTP_X_SCHOOL_SLUG=school.slug)
            client.force_authenticate(admin)
            try:
                response = client.put(url, {'outcome': 'missed', 'revision': 0}, format='json')
                return response.status_code
            finally:
                close_old_connections()

        with patch.object(LessonRecord.objects, 'create', side_effect=racing_create):
            with ThreadPoolExecutor(max_workers=2) as pool:
                statuses = list(pool.map(lambda _: save(), range(2)))
        self.assertEqual(sorted(statuses), [200, 201])
        self.assertEqual(LessonRecord.objects.count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action='lesson.outcome_recorded').count(), 1)
