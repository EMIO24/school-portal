from datetime import date
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from academics.models import AcademicSession, Term
from enrollment.models import ClassLevel, ClassArm, StudentProfile
from fees.models import FeeCategory, FeeSchedule, FeePayment
from tenants.models import School


class Batch17HFinanceHistoryTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name='Original School', slug='finance-hardening',
            subdomain='finance-hardening', subscription_plan='basic',
            motto='Original Motto')
        self.admin = CustomUser.objects.create_user(
            email='admin@finance-hardening.test', password='Password!26',
            role='school_admin', school=self.school, must_change_password=False)
        self.student_user = CustomUser.objects.create_user(
            email='student@finance-hardening.test', password='Password!26',
            first_name='Ada', last_name='Okafor', role='student',
            school=self.school, must_change_password=False)
        self.session = AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026,9,1), end_date=date(2027,7,30))
        self.term = Term.objects.create(
            session=self.session, name='first',
            start_date=date(2026,9,1), end_date=date(2026,12,18))
        self.level = ClassLevel.objects.create(school=self.school, name='JSS1')
        self.arm = ClassArm.objects.create(school=self.school, class_level=self.level, name='A')
        self.student = StudentProfile.objects.create(
            school=self.school, user=self.student_user, current_class=self.arm)
        self.category = FeeCategory.objects.create(school=self.school, name='Tuition')
        self.schedule = FeeSchedule.objects.create(
            school=self.school, term=self.term, class_level=self.level,
            fee_category=self.category, amount='10000.00')
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def pay(self):
        response = self.client.post('/api/fees/pay/manual/', {
            'student_id': self.student.pk,
            'fee_schedule_id': self.schedule.pk,
            'amount_paid': '4000.00',
            'payment_date': '2026-09-24',
            'method': 'bank_transfer',
            'idempotency_key': 'batch17h-payment-0001',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return FeePayment.objects.get(pk=response.data['id'])

    def test_used_fee_schedule_cannot_be_rewritten(self):
        self.pay()
        response = self.client.post('/api/fees/schedule/', {
            'term_id': self.term.pk,
            'schedules': [{
                'class_level_id': self.level.pk,
                'fee_category_id': self.category.pk,
                'amount': '15000.00',
            }],
        }, format='json')
        self.assertEqual(response.status_code, 207, response.data)
        self.schedule.refresh_from_db()
        self.assertEqual(str(self.schedule.amount), '10000.00')
        self.assertIn('financial history', response.data['errors'][0]['detail'])

    def test_unused_fee_schedule_remains_editable(self):
        response = self.client.post('/api/fees/schedule/', {
            'term_id': self.term.pk,
            'schedules': [{
                'class_level_id': self.level.pk,
                'fee_category_id': self.category.pk,
                'amount': '12000.00',
            }],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.schedule.refresh_from_db()
        self.assertEqual(str(self.schedule.amount), '12000.00')

    def test_receipt_snapshot_survives_later_record_changes(self):
        payment = self.pay()
        original = dict(payment.receipt_snapshot)
        self.category.name = 'Renamed Charge'
        self.category.save(update_fields=['name'])
        self.school.name = 'Renamed School'
        self.school.motto = 'Changed Motto'
        self.school.save(update_fields=['name', 'motto'])
        self.student_user.first_name = 'Changed'
        self.student_user.last_name = 'Name'
        self.student_user.save(update_fields=['first_name', 'last_name'])
        payment.refresh_from_db()
        self.assertEqual(payment.receipt_snapshot, original)
        self.assertEqual(payment.receipt_snapshot['school_name'], 'Original School')
        self.assertEqual(payment.receipt_snapshot['student_name'], 'Ada Okafor')
        self.assertEqual(payment.receipt_snapshot['fee_category'], 'Tuition')

        with patch('fees.views.render_to_string', side_effect=RuntimeError('force fallback')):
            response = self.client.get(f'/api/fees/receipts/{payment.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Original School', response.content)
        self.assertIn(b'Ada Okafor', response.content)
        self.assertIn(b'Tuition', response.content)
        self.assertNotIn(b'Renamed Charge', response.content)
