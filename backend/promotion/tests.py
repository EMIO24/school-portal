from django.test import TestCase

# Create your tests here.

from datetime import date
from decimal import Decimal

from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from accounts.models import CustomUser
from academics.models import AcademicSession, Term
from attendance.models import AttendanceRecord, AttendanceSession
from enrollment.models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile, Subject
from gradebook.models import ScoreEntry
from tenants.models import School

from .models import PromotionCriteria, PromotionRecord
from .services import evaluate_student
from .views import PromotionCriteriaView, PromotionEvaluateView, PromotionExecuteView


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


class PromotionEnrollmentHistoryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name='History School', slug='history-school',
            subdomain='history-school', subscription_plan='premium'
        )
        self.other = School.objects.create(
            name='Foreign History School', slug='foreign-history-school',
            subdomain='foreign-history-school', subscription_plan='premium'
        )
        self.admin = CustomUser.objects.create_user(
            'admin@history.test', 'Password!123',
            school=self.school, role='school_admin'
        )
        self.student_user = CustomUser.objects.create_user(
            'student@history.test', 'Password!123',
            school=self.school, role='student'
        )
        self.level1 = ClassLevel.objects.create(
            school=self.school, name='JSS1', order_index=1
        )
        self.level2 = ClassLevel.objects.create(
            school=self.school, name='JSS2', order_index=2
        )
        self.arm1 = ClassArm.objects.create(
            school=self.school, class_level=self.level1, name='A'
        )
        self.arm2 = ClassArm.objects.create(
            school=self.school, class_level=self.level2, name='A'
        )
        self.student = StudentProfile.objects.create(
            school=self.school, user=self.student_user,
            current_class=self.arm1, admission_number='HIST001'
        )
        self.source = AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31)
        )
        self.destination = AcademicSession.objects.create(
            school=self.school, name='2027/28',
            start_date=date(2027, 9, 1), end_date=date(2028, 7, 31)
        )
        self.source_enrollment = SessionEnrollment.objects.create(
            school=self.school, student=self.student,
            session=self.source, class_arm=self.arm1,
            enrolled_on=self.source.start_date,
            status='active', entry_reason='manual'
        )
        self.factory = APIRequestFactory()

    def execute(self, body):
        request = self.factory.post('/api/promotion/execute/', body, format='json')
        request.tenant = self.school
        force_authenticate(request, self.admin)
        return PromotionExecuteView.as_view(permission_classes=[])(request)

    def evaluate(self, session):
        request = self.factory.post(
            f'/api/promotion/evaluate/?session={session.pk}',
            {},
            format='json',
        )
        request.tenant = self.school
        force_authenticate(request, self.admin)
        return PromotionEvaluateView.as_view(permission_classes=[])(request)

    def promoted_body(self, **changes):
        item = {
            'student_id': self.student.pk,
            'session_id': self.source.pk,
            'to_session_id': self.destination.pk,
            'to_class_id': self.arm2.pk,
            'decision': 'promoted',
            'criteria_met': True,
        }
        item.update(changes)
        return [item]

    def test_promotion_closes_source_and_creates_destination_enrollment(self):
        response = self.execute(self.promoted_body())
        self.assertEqual(response.status_code, 200)

        self.source_enrollment.refresh_from_db()
        self.student.refresh_from_db()
        destination = SessionEnrollment.objects.get(
            student=self.student, session=self.destination
        )
        record = PromotionRecord.objects.get(
            student=self.student, from_session=self.source
        )

        self.assertEqual(self.source_enrollment.status, 'completed')
        self.assertEqual(self.source_enrollment.exited_on, self.source.end_date)
        self.assertEqual(destination.class_arm, self.arm2)
        self.assertEqual(destination.entry_reason, 'promotion')
        self.assertEqual(destination.status, 'active')
        self.assertEqual(record.from_class, self.arm1)
        self.assertEqual(record.to_class, self.arm2)
        self.assertEqual(self.student.current_class, self.arm2)

    def test_repeat_creates_new_session_enrollment_in_same_class(self):
        response = self.execute(self.promoted_body(
            decision='repeated',
            to_class_id=self.arm2.pk,
            criteria_met=False,
        ))
        self.assertEqual(response.status_code, 200)
        destination = SessionEnrollment.objects.get(
            student=self.student, session=self.destination
        )
        self.student.refresh_from_db()
        self.assertEqual(destination.class_arm, self.arm1)
        self.assertEqual(destination.entry_reason, 'repeat')
        self.assertEqual(self.student.current_class, self.arm1)

    def test_graduation_closes_history_and_clears_current_class(self):
        response = self.execute([{
            'student_id': self.student.pk,
            'session_id': self.source.pk,
            'decision': 'graduated',
            'criteria_met': True,
        }])
        self.assertEqual(response.status_code, 200)
        self.source_enrollment.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.source_enrollment.status, 'graduated')
        self.assertEqual(self.student.status, 'graduated')
        self.assertIsNone(self.student.current_class)
        self.assertFalse(
            SessionEnrollment.objects.filter(
                student=self.student, session=self.destination
            ).exists()
        )

    def test_historical_evaluation_uses_session_enrollment_not_current_class(self):
        self.student.current_class = self.arm2
        self.student.save(update_fields=['current_class'])
        response = self.evaluate(self.source)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['class'], self.arm1.full_name)
        self.assertEqual(response.data[0]['class_arm_id'], self.arm1.pk)
        self.assertEqual(response.data[0]['class_level_id'], self.level1.pk)

    def test_missing_historical_enrollment_fails_closed(self):
        self.source_enrollment.delete()
        response = self.execute(self.promoted_body())
        self.assertEqual(response.status_code, 400)
        self.assertIn('Historical class membership is missing', str(response.data))
        self.assertFalse(PromotionRecord.objects.exists())
        self.assertFalse(
            SessionEnrollment.objects.filter(
                student=self.student, session=self.destination
            ).exists()
        )

    def test_missing_current_session_enrollment_can_be_compatibility_created(self):
        self.source_enrollment.delete()
        self.source.is_current = True
        self.source.save(update_fields=['is_current'])
        response = self.execute(self.promoted_body())
        self.assertEqual(response.status_code, 200)
        old = SessionEnrollment.objects.get(
            student=self.student, session=self.source
        )
        self.assertEqual(old.entry_reason, 'migration')
        self.assertEqual(old.class_arm, self.arm1)
        self.assertEqual(old.status, 'completed')

    def test_foreign_destination_class_is_rejected(self):
        foreign_level = ClassLevel.objects.create(
            school=self.other, name='JSS2', order_index=2
        )
        foreign_arm = ClassArm.objects.create(
            school=self.other, class_level=foreign_level, name='A'
        )
        response = self.execute(self.promoted_body(to_class_id=foreign_arm.pk))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PromotionRecord.objects.exists())
        self.source_enrollment.refresh_from_db()
        self.assertEqual(self.source_enrollment.status, 'active')

    def test_existing_destination_enrollment_is_never_overwritten(self):
        SessionEnrollment.objects.create(
            school=self.school, student=self.student,
            session=self.destination, class_arm=self.arm2,
            enrolled_on=self.destination.start_date,
            status='active', entry_reason='manual'
        )
        response = self.execute(self.promoted_body())
        self.assertEqual(response.status_code, 400)
        self.assertIn('already has an enrollment', str(response.data))
        self.assertFalse(PromotionRecord.objects.exists())
        self.assertEqual(
            SessionEnrollment.objects.get(
                student=self.student, session=self.destination
            ).class_arm,
            self.arm2,
        )

    def test_one_invalid_student_rolls_back_entire_bulk_promotion(self):
        second_user = CustomUser.objects.create_user(
            'second@history.test', 'Password!123',
            school=self.school, role='student'
        )
        second = StudentProfile.objects.create(
            school=self.school, user=second_user,
            current_class=self.arm1, admission_number='HIST002'
        )
        second_enrollment = SessionEnrollment.objects.create(
            school=self.school, student=second,
            session=self.source, class_arm=self.arm1,
            enrolled_on=self.source.start_date,
            status='active', entry_reason='manual'
        )
        body = self.promoted_body() + [{
            'student_id': second.pk,
            'session_id': self.source.pk,
            'to_session_id': self.destination.pk,
            'to_class_id': self.arm1.pk,
            'decision': 'promoted',
            'criteria_met': True,
        }]

        response = self.execute(body)
        self.assertEqual(response.status_code, 400)
        self.source_enrollment.refresh_from_db()
        second_enrollment.refresh_from_db()
        self.student.refresh_from_db()
        second.refresh_from_db()

        self.assertEqual(self.source_enrollment.status, 'active')
        self.assertEqual(second_enrollment.status, 'active')
        self.assertEqual(self.student.current_class, self.arm1)
        self.assertEqual(second.current_class, self.arm1)
        self.assertFalse(PromotionRecord.objects.exists())
        self.assertFalse(
            SessionEnrollment.objects.filter(session=self.destination).exists()
        )
