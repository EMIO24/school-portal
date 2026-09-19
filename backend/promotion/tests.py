from django.test import TestCase

# Create your tests here.

from datetime import date
from decimal import Decimal

from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from accounts.models import CustomUser
from academics.models import AcademicSession, Term
from attendance.models import AttendanceRecord, AttendanceSession
from enrollment.models import ClassArm, ClassLevel, StudentProfile, Subject
from gradebook.models import ScoreEntry
from tenants.models import School

from .models import PromotionCriteria
from .services import evaluate_student
from .views import PromotionCriteriaView


class PromotionReadinessTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Promo School', slug='promo', subdomain='promo', subscription_plan='premium')
        self.other = School.objects.create(name='Other School', slug='otherpromo', subdomain='otherpromo', subscription_plan='premium')
        self.admin = CustomUser.objects.create_user('admin@promo.test', 'Password!123', school=self.school, role='school_admin')
        self.student_user = CustomUser.objects.create_user('student@promo.test', 'Password!123', school=self.school, role='student')
        self.teacher = CustomUser.objects.create_user('teacher@promo.test', 'Password!123', school=self.school, role='teacher')
        self.level = ClassLevel.objects.create(school=self.school, name='JSS1', order_index=1)
        self.other_level = ClassLevel.objects.create(school=self.other, name='Other JSS1', order_index=1)
        self.arm = ClassArm.objects.create(school=self.school, class_level=self.level, name='A')
        self.student = StudentProfile.objects.create(school=self.school, user=self.student_user, current_class=self.arm, admission_number='PROMO001')
        self.session = AcademicSession.objects.create(school=self.school, name='2026/27', start_date='2026-09-01', end_date='2027-07-31')
        self.term = Term.objects.create(session=self.session, name='first', start_date='2026-09-01', end_date='2026-12-31')
        self.subject = Subject.objects.create(school=self.school, name='Mathematics', code='MTH')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.headers = {'HTTP_X_SCHOOL_SLUG': 'promo'}
        self.factory = APIRequestFactory()

    def test_criteria_rejects_foreign_class_and_invalid_threshold(self):
        request = self.factory.post('/api/promotion/criteria/', {
            'class_level_id': self.other_level.pk,
            'min_attendance_pct': 50,
        }, format='json')
        request.tenant = self.school
        force_authenticate(request, self.admin)
        response = PromotionCriteriaView.as_view(permission_classes=[])(request)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PromotionCriteria.objects.filter(school=self.school, class_level=self.other_level).exists())

        request = self.factory.post('/api/promotion/criteria/', {
            'class_level_id': self.level.pk,
            'min_attendance_pct': 150,
        }, format='json')
        request.tenant = self.school
        force_authenticate(request, self.admin)
        response = PromotionCriteriaView.as_view(permission_classes=[])(request)
        self.assertEqual(response.status_code, 400)
        self.assertIn('min_attendance_pct', response.data)

    def test_promotion_attendance_matches_late_as_present_report_rule(self):
        ScoreEntry.objects.create(
            school=self.school,
            student=self.student_user,
            subject=self.subject,
            class_arm=self.arm,
            session=self.session,
            term=self.term,
            teacher=self.teacher,
            first_test=Decimal('10'),
            second_test=Decimal('10'),
            assignment=Decimal('10'),
            project=Decimal('5'),
            practical=Decimal('5'),
            exam_score=Decimal('50'),
            is_published=True,
        )
        attendance_session = AttendanceSession.objects.create(
            school=self.school,
            class_arm=self.arm,
            teacher=self.teacher,
            term=self.term,
            date=date(2026, 9, 15),
            is_finalized=True,
        )
        AttendanceRecord.objects.create(attendance_session=attendance_session, student=self.student_user, status='late')
        criteria = PromotionCriteria(
            school=self.school,
            class_level=self.level,
            min_subjects_to_pass=1,
            min_average_score=40,
            min_attendance_pct=100,
        )

        result = evaluate_student(self.student, self.session, criteria)
        self.assertEqual(result['attendance_pct'], 100)
        self.assertTrue(result['criteria_met'])
