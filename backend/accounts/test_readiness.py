from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.test.runner import DiscoverRunner
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from tenants.models import School
from academics.models import AcademicSession, Term
from enrollment.models import ClassLevel, ClassArm, Subject, StudentProfile
from gradebook.models import ScoreEntry
from cbt.models import Question, CBTExam, StudentExamSession, StudentAnswer
from notifications.models import NotificationLog

class ReadinessChecks(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = School.objects.create(name='Audit A', slug='audit-a', subdomain='audit-a', subscription_plan='premium')
        cls.b = School.objects.create(name='Audit B', slug='audit-b', subdomain='audit-b', subscription_plan='premium')
        def user(name, role, school):
            return get_user_model().objects.create_user(email=name+'@audit.invalid', password='Audit-only-password!26', role=role, school=school, must_change_password=False)
        cls.student = user('student', 'student', cls.a)
        cls.other = user('other', 'student', cls.b)
        cls.admin = user('admin', 'school_admin', cls.b)
        cls.level = ClassLevel.objects.create(school=cls.b, name='JSS1')
        cls.arm = ClassArm.objects.create(school=cls.b, class_level=cls.level, name='A')
        cls.subject = Subject.objects.create(school=cls.b, name='Math', code='MATH')
        cls.session = AcademicSession.objects.create(school=cls.b, name='2026/2027', start_date=date(2026,9,1), end_date=date(2027,7,31))
        cls.term = Term.objects.create(session=cls.session, name='first', start_date=date(2026,9,1), end_date=date(2026,12,18))
        StudentProfile.objects.create(user=cls.other, school=cls.b, current_class=cls.arm)
        cls.entry = ScoreEntry.objects.create(school=cls.b, student=cls.other, subject=cls.subject, class_arm=cls.arm, term=cls.term, session=cls.session, exam_score=40)
        cls.question = Question.objects.create(school=cls.b, subject=cls.subject, class_level=cls.level, question_text='Audit question', correct_answer='A', options=[{'id':'A','text':'Yes'},{'id':'B','text':'No'}])
        cls.exam = CBTExam.objects.create(school=cls.b, title='Future exam', subject=cls.subject, term=cls.term, session=cls.session, start_datetime=timezone.now()+timedelta(days=1), end_datetime=timezone.now()+timedelta(days=2), duration_minutes=10, selection_mode='manual', status='published', randomize_options=False)
        cls.exam.manual_questions.add(cls.question)
        cls.exam.class_arms.add(cls.arm)
    def client_for(self, user, school):
        client = APIClient(HTTP_X_SCHOOL_SLUG=school.slug)
        client.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(user).access_token))
        return client
    def test_cross_school_gradebook_read_denied(self):
        r = self.client_for(self.student, self.b).get('/api/gradebook/entries/')
        self.assertIn(r.status_code, (403,404), 'Another school student can read gradebook')
    def test_student_cannot_delete_grade(self):
        r = self.client_for(self.other, self.b).delete(f'/api/gradebook/entries/{self.entry.pk}/')
        self.assertIn(r.status_code, (403,404,405), 'Student deleted a grade')
    def test_cross_school_question_answers_denied(self):
        r = self.client_for(self.student, self.b).get(f'/api/cbt/questions/{self.question.pk}/')
        self.assertFalse(r.status_code == 200 and 'correct_answer' in r.data, 'Answer key leaked across schools')
    def test_cross_school_notification_logs_denied(self):
        NotificationLog.objects.create(school=self.b, channel='sms', recipient_phone='08000000000', message_body='Synthetic private message')
        r = self.client_for(self.student, self.b).get('/api/notifications/logs/')
        self.assertIn(r.status_code, (403,404), 'Other school student can read notification logs')
    def test_exam_cannot_start_before_schedule(self):
        r = self.client_for(self.other, self.b).post(f'/api/cbt/exams/{self.exam.pk}/start/', {}, format='json')
        self.assertIn(r.status_code, (400,403), 'Future exam started early')
    def test_unassigned_cross_school_student_cannot_start_exam(self):
        r = self.client_for(self.student, self.b).post(f'/api/cbt/exams/{self.exam.pk}/start/', {}, format='json')
        self.assertIn(r.status_code, (400,403,404), 'Unassigned foreign student started exam')
    def test_expired_exam_rejects_answers(self):
        run = StudentExamSession.objects.create(exam=self.exam, student=self.other, status='in_progress', started_at=timezone.now()-timedelta(hours=1), question_order=[self.question.pk])
        r = self.client_for(self.other, self.b).post(f'/api/cbt/exams/{self.exam.pk}/save-answer/', {'question_id':self.question.pk,'selected_option':'A'}, format='json')
        self.assertFalse(StudentAnswer.objects.filter(exam_session=run).exists(), f'Late answer persisted; HTTP {r.status_code}')
    def test_decimal_score_has_valid_grade_band(self):
        self.entry.exam_score = Decimal('54.50')
        self.entry.save()
        self.assertNotEqual(self.entry.grade, 'F9', '54.50 falls through grade bands to Fail')
    def bulk(self, student, mark):
        return self.client_for(self.admin, self.b).post('/api/gradebook/entries/bulk-update/', {'class_arm':self.arm.pk,'subject':self.subject.pk,'term':self.term.pk,'session':self.session.pk,'scores':[{'student_id':student.pk,'exam_score':mark}]}, format='json')
    def test_bulk_scores_reject_foreign_student(self):
        r = self.bulk(self.student, 30)
        self.assertFalse(ScoreEntry.objects.filter(school=self.b, student=self.student).exists(), f'Foreign student linked to grade; HTTP {r.status_code}')
    def test_bulk_scores_reject_negative_marks(self):
        r = self.bulk(self.other, -10)
        self.entry.refresh_from_db()
        self.assertGreaterEqual(self.entry.exam_score, 0, f'Negative mark persisted; HTTP {r.status_code}')
    def test_failed_otp_delivery_not_reported_as_sent(self):
        with patch('notifications.services.termii.TermiiService.send_sms', return_value=(False, 'Provider unavailable')):
            r = APIClient(HTTP_X_SCHOOL_SLUG=self.a.slug).post('/api/auth/parent/otp-request/', {'phone':'08000000000'}, format='json')
        self.assertFalse(r.status_code == 200 and r.data.get('detail') == 'OTP sent.', 'Failed delivery reported as sent')

    def test_refresh_token_cannot_be_reused_after_rotation(self):
        token = str(RefreshToken.for_user(self.other))
        c = APIClient()
        first = c.post('/api/auth/token/refresh/', {'refresh':token}, format='json')
        self.assertEqual(first.status_code, 200)
        second = c.post('/api/auth/token/refresh/', {'refresh':token}, format='json')
        self.assertEqual(second.status_code, 401, 'Rotated refresh token remains reusable')
    def test_password_change_revokes_old_refresh(self):
        token = str(RefreshToken.for_user(self.other))
        self.other.set_password('Replacement-audit-password!26')
        self.other.save(update_fields=['password'])
        r = APIClient().post('/api/auth/token/refresh/', {'refresh':token}, format='json')
        self.assertEqual(r.status_code, 401, 'Old refresh token survives password change')
    def test_paid_category_cannot_erase_receipts(self):
        from fees.models import FeeCategory, FeeSchedule, FeePayment
        category = FeeCategory.objects.create(school=self.b, name='Tuition')
        schedule = FeeSchedule.objects.create(school=self.b, term=self.term, class_level=self.level, fee_category=category, amount=100)
        payment = FeePayment.objects.create(school=self.b, student=self.other.student_profile, fee_schedule=schedule, amount_paid=100, payment_date=date.today(), method='cash')
        r = self.client_for(self.admin, self.b).delete(f'/api/fees/categories/{category.pk}/')
        self.assertTrue(FeePayment.objects.filter(pk=payment.pk).exists(), f'Category deletion erased receipt; HTTP {r.status_code}')
    def test_otp_text_not_exposed_through_notification_logs(self):
        from unittest.mock import Mock
        with patch('notifications.services.termii.requests.post', return_value=Mock()):
            APIClient(HTTP_X_SCHOOL_SLUG=self.b.slug).post('/api/auth/parent/otp-request/', {'phone':'08000000000'}, format='json')
        r = self.client_for(self.student, self.b).get('/api/notifications/logs/')
        self.assertFalse(r.status_code == 200 and any('login code is' in row.get('message_body','') for row in r.data), 'Parent OTP text readable by another school student')

    def test_public_result_checker_reaches_input_validation(self):
        r = APIClient(HTTP_X_SCHOOL_SLUG=self.b.slug).post('/api/results/check/', {}, format='json')
        self.assertEqual(r.status_code, 400, 'Plan middleware blocks the public result checker before its view')

