from datetime import date, time

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from academics.models import AcademicSession, Term
from enrollment.models import ClassLevel, ClassArm, StaffProfile, Subject, SubjectAssignment
from tenants.models import School
from timetable.models import Period, TimetableEntry, LessonRecord


class Batch17HAssignmentAndPrivacyTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name='Hardening School', slug='hardening-school',
            subdomain='hardening-school', subscription_plan='basic')
        self.admin = CustomUser.objects.create_user(
            email='admin@hardening.test', password='Password!26',
            role='school_admin', school=self.school, must_change_password=False)
        self.teacher = CustomUser.objects.create_user(
            email='teacher@hardening.test', password='Password!26',
            role='teacher', school=self.school, must_change_password=False)
        self.student = CustomUser.objects.create_user(
            email='student@hardening.test', password='Password!26',
            role='student', school=self.school, must_change_password=False)
        self.parent = CustomUser.objects.create_user(
            email='parent@hardening.test', password='Password!26',
            role='parent', school=self.school, must_change_password=False)
        self.staff = StaffProfile.objects.create(school=self.school, user=self.teacher)
        self.session = AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026,9,1), end_date=date(2027,7,30))
        self.term = Term.objects.create(
            session=self.session, name='first',
            start_date=date(2026,9,1), end_date=date(2026,12,18))
        self.level = ClassLevel.objects.create(school=self.school, name='JSS1')
        self.arm = ClassArm.objects.create(school=self.school, class_level=self.level, name='A')
        self.subject = Subject.objects.create(school=self.school, name='Mathematics', code='MTH')
        self.assignment = SubjectAssignment.objects.create(
            school=self.school, teacher=self.staff, subject=self.subject,
            class_arm=self.arm, session=self.session, term=self.term)
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def add_history(self):
        period = Period.objects.create(
            school=self.school, name='Period 1',
            start_time=time(8), end_time=time(9), order_index=1)
        slot = TimetableEntry.objects.create(
            school=self.school, term=self.term, class_arm=self.arm,
            subject=self.subject, teacher=self.teacher,
            day_of_week='MON', period=period)
        LessonRecord.objects.create(
            school=self.school, timetable_entry=slot, slot_id=slot.pk,
            date=date(2026,9,21), term=self.term, term_name=str(self.term),
            class_arm_id_snapshot=self.arm.pk, class_name=self.arm.full_name,
            subject_id_snapshot=self.subject.pk, subject_name=self.subject.name,
            period_name=period.name, period_start=period.start_time, period_end=period.end_time,
            scheduled_teacher_id=self.teacher.pk, scheduled_teacher_name=self.teacher.full_name,
            actual_teacher=self.teacher, actual_teacher_name=self.teacher.full_name,
            outcome='delivered', recorded_by=self.teacher)

    def test_historical_subject_assignment_cannot_be_deleted(self):
        self.add_history()
        response = self.client.delete(f'/api/subject-assignments/{self.assignment.pk}/')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(SubjectAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_bulk_replacement_cannot_remove_historical_assignment(self):
        self.add_history()
        response = self.client.post(f'/api/staff/{self.staff.pk}/assign-subjects/', {
            'session_id': self.session.pk, 'term_id': self.term.pk, 'assignments': []
        }, format='json')
        self.assertEqual(response.status_code, 409, response.data)
        self.assertIn(self.assignment.pk, response.data['protected_assignment_ids'])
        self.assertTrue(SubjectAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_unused_assignment_can_still_be_corrected(self):
        response = self.client.delete(f'/api/subject-assignments/{self.assignment.pk}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(SubjectAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_students_and_parents_cannot_browse_staff_directory(self):
        for user in (self.student, self.parent):
            self.client.force_authenticate(user)
            with self.subTest(role=user.role):
                self.assertEqual(self.client.get('/api/staff/').status_code, 403)
                self.assertEqual(self.client.get(f'/api/staff/{self.staff.pk}/').status_code, 403)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get('/api/staff/').status_code, 200)

    def test_suspended_teacher_has_no_assigned_classes_helper_access(self):
        from accounts.school_access import assigned_classes
        from rest_framework.test import APIRequestFactory, force_authenticate
        self.staff.employment_status = 'suspended'
        self.staff.save(update_fields=['employment_status'])
        request = APIRequestFactory().get('/api/attendance/sessions/')
        request.tenant = self.school
        force_authenticate(request, user=self.teacher)
        request.user = self.teacher
        self.assertEqual(list(assigned_classes(request)), [])
