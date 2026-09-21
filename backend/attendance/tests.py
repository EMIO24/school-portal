from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tenants.models import School
from academics.models import AcademicSession, Term
from enrollment.models import ClassLevel, ClassArm, StudentProfile
from attendance.models import AttendanceSession, AttendanceRecord
from accounts.models import ParentStudentLink


class StudentAttendanceReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # School
        cls.school = School.objects.create(
            name='Attendance Test School',
            slug='attendance-test',
            subdomain='attendance-test',
            subscription_plan='basic',
        )

        # Academic structure
        cls.session = AcademicSession.objects.create(
            school=cls.school,
            name='2026/2027',
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
        )

        cls.term = Term.objects.create(
            session=cls.session,
            name='first',
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 18),
        )

        cls.level = ClassLevel.objects.create(
            school=cls.school,
            name='JSS1',
        )

        cls.arm = ClassArm.objects.create(
            school=cls.school,
            class_level=cls.level,
            name='A',
        )

        User = get_user_model()

        # Two students in the same school.
        cls.student_a = User.objects.create_user(
            email='student-a@attendance.invalid',
            password='Attendance-test-password!26',
            role='student',
            school=cls.school,
            must_change_password=False,
        )

        cls.student_b = User.objects.create_user(
            email='student-b@attendance.invalid',
            password='Attendance-test-password!26',
            role='student',
            school=cls.school,
            must_change_password=False,
        )

        # Parent linked only to Student A.
        cls.parent = User.objects.create_user(
            email='parent@attendance.invalid',
            password='Attendance-test-password!26',
            role='parent',
            school=cls.school,
            must_change_password=False,
        )

        cls.profile_a = StudentProfile.objects.create(
            user=cls.student_a,
            school=cls.school,
            current_class=cls.arm,
        )

        cls.profile_b = StudentProfile.objects.create(
            user=cls.student_b,
            school=cls.school,
            current_class=cls.arm,
        )

        ParentStudentLink.objects.create(
            parent=cls.parent,
            student=cls.profile_a,
            school=cls.school,
            relationship='guardian',
        )
        # One attendance session containing records for both students.
        cls.attendance_session = AttendanceSession.objects.create(
            school=cls.school,
            class_arm=cls.arm,
            term=cls.term,
            date=date(2026, 9, 15),
            mode='daily',
        )

        cls.record_a = AttendanceRecord.objects.create(
            attendance_session=cls.attendance_session,
            student=cls.student_a,
            status='present',
            remark='',
        )

        cls.record_b = AttendanceRecord.objects.create(
            attendance_session=cls.attendance_session,
            student=cls.student_b,
            status='absent',
            remark='Test absence',
        )

        # A student belonging to another school.
        cls.other_school = School.objects.create(
            name='Other Attendance School',
            slug='other-attendance-test',
            subdomain='other-attendance-test',
            subscription_plan='basic',
        )

        cls.foreign_student = User.objects.create_user(
            email='foreign-student@attendance.invalid',
            password='Attendance-test-password!26',
            role='student',
            school=cls.other_school,
            must_change_password=False,
        )

    def client_for(self, user):
        client = APIClient(
            HTTP_X_SCHOOL_SLUG=self.school.slug
        )

        token = RefreshToken.for_user(user).access_token

        client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + str(token)
        )

        return client

    def test_student_can_read_own_attendance_records(self):
        response = self.client_for(self.student_a).get(
            '/api/attendance/sessions/student-report/',
            {
                'student': self.student_a.pk,
                'term': self.term.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['status'],
            'present',
        )
        self.assertEqual(
            response.data[0]['session_id'],
            self.attendance_session.pk,
        )

    def test_student_cannot_read_another_students_attendance(self):
        response = self.client_for(self.student_a).get(
            '/api/attendance/sessions/student-report/',
            {
                'student': self.student_b.pk,
                'term': self.term.pk,
            },
        )

        self.assertIn(
            response.status_code,
            (403, 404),
        )

    def test_linked_parent_can_read_child_attendance(self):
        response = self.client_for(self.parent).get(
            '/api/attendance/sessions/student-report/',
            {
                'student': self.student_a.pk,
                'term': self.term.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]['status'],
            'present',
        )

    def test_parent_cannot_read_unlinked_student_attendance(self):
        response = self.client_for(self.parent).get(
            '/api/attendance/sessions/student-report/',
            {
                'student': self.student_b.pk,
                'term': self.term.pk,
            },
        )

        self.assertIn(
            response.status_code,
            (403, 404),
        )

    def test_cross_school_student_cannot_read_attendance(self):
        client = APIClient(
            HTTP_X_SCHOOL_SLUG=self.school.slug
        )

        token = RefreshToken.for_user(
            self.foreign_student
        ).access_token

        client.credentials(
            HTTP_AUTHORIZATION='Bearer ' + str(token)
        )

        response = client.get(
            '/api/attendance/sessions/student-report/',
            {
                'student': self.student_a.pk,
                'term': self.term.pk,
            },
        )

        self.assertIn(
            response.status_code,
            (403, 404),
        )