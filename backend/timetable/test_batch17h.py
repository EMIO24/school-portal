from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser, ParentStudentLink
from academics.models import AcademicSession, Term
from enrollment.models import ClassLevel, ClassArm, StudentProfile, StaffProfile, Subject
from tenants.models import School
from timetable.models import Period, TimetableEntry


class Batch17HTimetableAccessTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name='Timetable Hardening', slug='tt-hardening',
            subdomain='tt-hardening', subscription_plan='basic')
        self.admin = CustomUser.objects.create_user(
            email='admin@tt-hardening.test', password='Password!26',
            role='school_admin', school=self.school, must_change_password=False)
        self.teacher_a = CustomUser.objects.create_user(
            email='teachera@tt-hardening.test', password='Password!26',
            role='teacher', school=self.school, must_change_password=False)
        self.teacher_b = CustomUser.objects.create_user(
            email='teacherb@tt-hardening.test', password='Password!26',
            role='teacher', school=self.school, must_change_password=False)
        StaffProfile.objects.create(school=self.school, user=self.teacher_a)
        StaffProfile.objects.create(school=self.school, user=self.teacher_b)
        self.student_user = CustomUser.objects.create_user(
            email='student@tt-hardening.test', password='Password!26',
            role='student', school=self.school, must_change_password=False)
        self.parent = CustomUser.objects.create_user(
            email='parent@tt-hardening.test', password='Password!26',
            role='parent', school=self.school, must_change_password=False)
        self.session = AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026,9,1), end_date=date(2027,7,30))
        self.term = Term.objects.create(
            session=self.session, name='first',
            start_date=date(2026,9,1), end_date=date(2026,12,18))
        self.level = ClassLevel.objects.create(school=self.school, name='JSS1')
        self.arm_a = ClassArm.objects.create(school=self.school, class_level=self.level, name='A')
        self.arm_b = ClassArm.objects.create(school=self.school, class_level=self.level, name='B')
        self.student = StudentProfile.objects.create(
            school=self.school, user=self.student_user, current_class=self.arm_a)
        ParentStudentLink.objects.create(
            school=self.school, parent=self.parent, student=self.student, relationship='guardian')
        self.subject = Subject.objects.create(school=self.school, name='Mathematics', code='MTH')
        self.period = Period.objects.create(
            school=self.school, name='Period 1', start_time=time(8), end_time=time(9), order_index=1)
        self.entry_a = TimetableEntry.objects.create(
            school=self.school, term=self.term, class_arm=self.arm_a, subject=self.subject,
            teacher=self.teacher_a, day_of_week='MON', period=self.period)
        self.period2 = Period.objects.create(
            school=self.school, name='Period 2', start_time=time(9), end_time=time(10), order_index=2)
        self.entry_b = TimetableEntry.objects.create(
            school=self.school, term=self.term, class_arm=self.arm_b, subject=self.subject,
            teacher=self.teacher_b, day_of_week='MON', period=self.period2)
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)

    def ids(self, user):
        self.client.force_authenticate(user)
        response = self.client.get('/api/timetable/entries/')
        self.assertEqual(response.status_code, 200, response.data)
        rows = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        return {row['id'] for row in rows}

    def test_student_only_sees_current_class_timetable(self):
        self.assertEqual(self.ids(self.student_user), {self.entry_a.pk})
        response = self.client.get(f'/api/timetable/entries/by-class/{self.arm_b.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_parent_only_sees_linked_child_class_timetable(self):
        self.assertEqual(self.ids(self.parent), {self.entry_a.pk})
        response = self.client.get(f'/api/timetable/entries/by-class/{self.arm_b.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_teacher_only_sees_own_timetable(self):
        self.assertEqual(self.ids(self.teacher_a), {self.entry_a.pk})
        response = self.client.get(f'/api/timetable/entries/by-teacher/{self.teacher_b.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_teacher_load_is_admin_only(self):
        for user in (self.teacher_a, self.student_user, self.parent):
            self.client.force_authenticate(user)
            with self.subTest(role=user.role):
                response = self.client.get(
                    f'/api/timetable/entries/teacher-load/?teacher={self.teacher_a.pk}&term={self.term.pk}')
                self.assertEqual(response.status_code, 403)
        self.client.force_authenticate(self.admin)
        response = self.client.get(
            f'/api/timetable/entries/teacher-load/?teacher={self.teacher_a.pk}&term={self.term.pk}')
        self.assertEqual(response.status_code, 200)
