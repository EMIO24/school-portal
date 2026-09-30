"""PostgreSQL finance invariants and tenant-facing ledger contracts."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import CustomUser, ParentStudentLink
from academics.models import AcademicSession, Term
from enrollment.models import ClassArm, ClassLevel, StudentProfile
from tenants.models import School
from .ledger import account_balance, generate_charges, post_adjustment
from .models import FeeCategory, FeePayment, FeeSchedule, StudentLedgerEntry, StudentPaymentAllocation


class LedgerFixture:
    def setUp(self):
        self.school = School.objects.create(name='Ledger School', slug='ledger-school', subdomain='ledger-school', subscription_plan='basic')
        self.other = School.objects.create(name='Foreign School', slug='foreign-school', subdomain='foreign-school')
        self.admin = CustomUser.objects.create_user('admin@ledger.test', 'Password!123', school=self.school, role='school_admin')
        self.parent = CustomUser.objects.create_user('parent@ledger.test', 'Password!123', school=self.school, role='parent')
        self.user = CustomUser.objects.create_user('student@ledger.test', 'Password!123', school=self.school, role='student')
        level = ClassLevel.objects.create(school=self.school, name='JSS1', order_index=1)
        self.arm = ClassArm.objects.create(school=self.school, class_level=level, name='A')
        self.student = StudentProfile.objects.create(school=self.school, user=self.user, current_class=self.arm, admission_number='LED001')
        session = AcademicSession.objects.create(school=self.school, name='2026/27', start_date='2026-09-01', end_date='2027-07-31')
        self.term = Term.objects.create(session=session, name='first', start_date='2026-09-01', end_date='2026-12-31')
        category = FeeCategory.objects.create(school=self.school, name='Tuition')
        self.schedule = FeeSchedule.objects.create(school=self.school, term=self.term, class_level=level,
            fee_category=category, amount=Decimal('1000.00'))
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.headers = {'HTTP_X_SCHOOL_SLUG': self.school.slug}

    def payment(self, amount, key='ledger-payment-0001', **extra):
        return self.client.post('/api/fees/pay/manual/', {'student_id': self.student.pk,
            'fee_schedule_id': self.schedule.pk, 'amount_paid': str(amount),
            'payment_date': '2026-09-27', 'method': 'cash', 'idempotency_key': key, **extra},
            format='json', **self.headers)


class StudentLedgerTests(LedgerFixture, TestCase):
    def test_charge_snapshot_duplicate_safe_and_payment_allocation(self):
        first = generate_charges(self.school, self.term, self.admin)
        again = generate_charges(self.school, self.term, self.admin)
        self.assertEqual((first['created'], again['created']), (1, 0))
        # Simulate out-of-band/legacy drift that bypasses FeeSchedule.save().
        # Normal application writes are intentionally blocked by Batch 17H.
        FeeSchedule.objects.filter(pk=self.schedule.pk).update(amount=Decimal('1900.00'))
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.amount, Decimal('1900.00'))
        first_payment = self.payment('400.00')
        self.assertEqual(first_payment.status_code, 201, first_payment.content)
        self.assertEqual(self.payment('400.00').status_code, 200)
        self.assertEqual(self.payment('600.00', key='ledger-payment-0002').status_code, 201)
        charge = StudentLedgerEntry.objects.get(student=self.student, kind='charge')
        self.assertEqual(charge.signed_amount, Decimal('1000.00'))
        self.assertEqual(FeePayment.objects.filter(student=self.student).count(), 2)
        self.assertEqual(sum(StudentPaymentAllocation.objects.values_list('amount', flat=True)), Decimal('1000.00'))
        self.assertEqual(account_balance(self.school, self.student)['outstanding'], Decimal('0.00'))

    def test_opening_discount_scholarship_adjustment_credit_and_conflicting_replay(self):
        self.assertEqual(self.client.post('/api/fees/ledger/changes/', {'student_id': self.student.pk,
            'kind': 'opening', 'amount': '100.00', 'reason': 'Verified prior debt',
            'effective_date': '2026-08-31', 'idempotency_key': 'opening-0001'}, format='json', **self.headers).status_code, 201)
        generate_charges(self.school, self.term, self.admin)
        for kind, amount, key in [('discount', '50.00', 'discount-0001'),
                                  ('scholarship', '100.00', 'scholarship-0001')]:
            data = {'student_id': self.student.pk, 'fee_schedule_id': self.schedule.pk,
                'kind': kind, 'amount': amount, 'reason': 'Authorized award', 'idempotency_key': key}
            self.assertEqual(self.client.post('/api/fees/ledger/changes/', data, format='json', **self.headers).status_code, 201)
            self.assertEqual(self.client.post('/api/fees/ledger/changes/', data, format='json', **self.headers).status_code, 200)
            self.assertEqual(self.client.post('/api/fees/ledger/changes/', {**data, 'amount': '1.00'},
                format='json', **self.headers).status_code, 409)
        summary = self.client.get(f'/api/fees/student/{self.student.pk}/?term={self.term.pk}', **self.headers).data[0]
        self.assertEqual(summary['paid'], Decimal('0.00'))
        self.assertEqual(summary['credits'], Decimal('150.00'))
        self.assertEqual(summary['outstanding'], Decimal('850.00'))
        self.assertEqual(self.payment('1000.00', allow_credit=True).status_code, 201)
        self.assertEqual(account_balance(self.school, self.student)['credit'], Decimal('50.00'))
        self.assertEqual(self.payment('1.00', key='ledger-payment-0001', allow_credit=True).status_code, 409)

    def test_unknown_and_legacy_review_are_not_zero(self):
        self.assertIsNone(account_balance(self.school, self.student)['outstanding'])
        FeePayment.objects.create(school=self.school, student=self.student, fee_schedule=self.schedule,
            amount_paid=Decimal('20.00'), payment_date=date.today(), method='cash')
        self.assertEqual(account_balance(self.school, self.student)['state'], 'legacy_review')
        self.assertIsNone(account_balance(self.school, self.student)['balance'])
        response = self.client.get('/api/fees/ledger/accounts/', **self.headers)
        self.assertEqual(response.data['results'][0]['state'], 'legacy_review')
        self.assertIsNone(response.data['results'][0]['outstanding'])

    def test_legacy_opening_does_not_double_charge_the_old_term(self):
        FeePayment.objects.create(school=self.school, student=self.student, fee_schedule=self.schedule,
            amount_paid=Decimal('200.00'), payment_date=date(2026, 9, 10), method='cash')
        result = generate_charges(self.school, self.term, self.admin)
        self.assertEqual((result['created'], result['legacy_skipped']), (0, 1))
        opening = self.client.post('/api/fees/ledger/changes/', {'student_id': self.student.pk,
            'kind': 'opening', 'amount': '800.00', 'reason': 'Verified after old receipt',
            'effective_date': '2026-09-20', 'idempotency_key': 'legacy-opening-0001'},
            format='json', **self.headers)
        self.assertEqual(opening.status_code, 201)
        self.assertEqual(generate_charges(self.school, self.term, self.admin)['created'], 0)
        self.assertEqual(self.payment('300.00', key='legacy-payment-0001').status_code, 201)
        self.assertEqual(StudentLedgerEntry.objects.filter(student=self.student, kind='charge').count(), 0)
        self.assertEqual(account_balance(self.school, self.student)['outstanding'], Decimal('500.00'))

    def test_debtor_totals_are_independent_of_page_and_zero_is_known(self):
        generate_charges(self.school, self.term, self.admin)
        response = self.client.get('/api/fees/ledger/debtors/', **self.headers)
        self.assertEqual(response.data['summary']['total_outstanding'], Decimal('1000.00'))
        self.assertEqual(response.data['summary']['debtor_count'], 1)
        self.payment('1000.00')
        response = self.client.get('/api/fees/ledger/debtors/', **self.headers)
        self.assertEqual(response.data['summary']['total_outstanding'], Decimal('0.00'))
        self.assertEqual(response.data['summary']['debtor_count'], 0)

    def test_account_list_query_count_stays_bounded(self):
        generate_charges(self.school, self.term, self.admin)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f'/api/fees/outstanding/?term={self.term.pk}', **self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(queries), 7, len(queries))

    def test_student_parent_and_foreign_tenant_access(self):
        generate_charges(self.school, self.term, self.admin)
        url = f'/api/fees/ledger/student/{self.student.pk}/'
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(url, **self.headers).status_code, 200)
        self.assertEqual(self.client.post('/api/fees/ledger/charges/', {}, format='json', **self.headers).status_code, 403)
        self.client.force_authenticate(self.parent)
        self.assertIn(self.client.get(url, **self.headers).status_code, (403, 404))
        ParentStudentLink.objects.create(school=self.school, parent=self.parent, student=self.student)
        self.assertEqual(self.client.get(url, **self.headers).status_code, 200)
        self.assertIn(self.client.get(url, HTTP_X_SCHOOL_SLUG=self.other.slug).status_code, (403, 404))
        self.client.force_authenticate(self.admin)
        self.assertIn(self.client.post('/api/fees/ledger/changes/', {'student_id': self.student.pk,
            'kind': 'discount', 'fee_schedule_id': 999999, 'amount': '1.00',
            'reason': 'foreign', 'idempotency_key': 'foreign-00001'},
            format='json', **self.headers).status_code, (400, 404))

    def test_invalid_money_and_reason_rejected(self):
        generate_charges(self.school, self.term, self.admin)
        for value in ('NaN', '-1', '1.001', '999999999999999999999'):
            response = self.client.post('/api/fees/ledger/changes/', {'student_id': self.student.pk,
                'kind': 'discount', 'fee_schedule_id': self.schedule.pk, 'amount': value,
                'reason': 'Test', 'idempotency_key': 'invalid-00001'}, format='json', **self.headers)
            self.assertEqual(response.status_code, 400)
        self.assertFalse(StudentLedgerEntry.objects.filter(kind='discount').exists())
        self.assertEqual(self.client.post('/api/fees/ledger/charges/',
            {'term_id': 'not-a-term'}, format='json', **self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/fees/ledger/changes/',
            {'student_id': 'not-a-student', 'kind': 'adjustment', 'amount': '1.00',
             'reason': 'Bad ID', 'idempotency_key': 'bad-id-0001'},
            format='json', **self.headers).status_code, 400)
        self.assertEqual(self.client.get('/api/fees/ledger/debtors/?class_arm=wrong',
            **self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/fees/pay/manual/', {
            'student_id': 'wrong', 'fee_schedule_id': self.schedule.pk,
            'amount_paid': '1.00', 'payment_date': '2026-09-27'},
            format='json', **self.headers).status_code, 400)
        self.assertEqual(self.client.post('/api/fees/ledger/changes/', {
            'student_id': self.student.pk, 'kind': 'adjustment', 'amount': '1.00',
            'reason': 'Bad reference', 'reference': 'x' * 101,
            'idempotency_key': 'bad-reference-0001'}, format='json', **self.headers).status_code, 400)

    def test_guided_opening_import_previews_reuses_and_rejects_changed_value(self):
        body = ('student_ref,amount,direction,effective_date,reason,reference\n'
                'LED001,250.00,debt,2026-09-01,Verified old balance,legacy-book-42\n')
        def upload(operation, csv_body):
            return self.client.post(f'/api/migration/opening_balances/{operation}/', {
                'file': SimpleUploadedFile('opening.csv', csv_body.encode(), content_type='text/csv'),
                'mapping': '{}'}, format='multipart', **self.headers)
        preview = upload('validate', body)
        self.assertEqual(preview.data['counts']['CREATE'], 1)
        self.assertFalse(StudentLedgerEntry.objects.exists())
        with patch('enrollment.migration_import.post_adjustment', side_effect=ValueError('Account changed during import')):
            rejected = upload('import', body)
        self.assertEqual(rejected.data['counts']['REJECT'], 1)
        self.assertEqual(rejected.data['rows'][0]['field'], 'student_ref')
        self.assertFalse(StudentLedgerEntry.objects.exists())
        self.assertEqual(upload('import', body).data['counts']['CREATE'], 1)
        self.assertEqual(upload('import', body).data['counts']['REUSE'], 1)
        self.assertEqual(account_balance(self.school, self.student)['outstanding'], Decimal('250.00'))
        self.assertEqual(upload('validate', body.replace('250.00', '260.00')).data['counts']['REJECT'], 1)
        self.assertEqual(upload('validate', body.replace('LED001', 'FOREIGN')).data['counts']['REJECT'], 1)
        self.assertEqual(StudentLedgerEntry.objects.filter(kind='opening').count(), 1)


class LedgerConcurrencyTests(LedgerFixture, TransactionTestCase):
    def test_duplicate_charge_and_adjustment_races(self):
        def generate(_):
            close_old_connections()
            try: return generate_charges(self.school, self.term, self.admin)['created']
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(generate, range(2))), 1)
        def adjust(_):
            close_old_connections()
            try:
                return post_adjustment(self.school, self.student, self.admin, kind='discount',
                    amount='25.00', reason='Race test', key='race-discount-0001', schedule=self.schedule)[1]
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(adjust, range(2))), 1)
        self.assertEqual(StudentLedgerEntry.objects.filter(student=self.student).count(), 2)

    def test_duplicate_payment_race_creates_one_receipt_and_one_ledger_credit(self):
        generate_charges(self.school, self.term, self.admin)
        def pay(_):
            close_old_connections()
            try:
                client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
                client.force_authenticate(self.admin)
                response = client.post('/api/fees/pay/manual/', {'student_id': self.student.pk,
                    'fee_schedule_id': self.schedule.pk, 'amount_paid': '400.00',
                    'payment_date': '2026-09-27', 'method': 'cash',
                    'idempotency_key': 'parallel-payment-0001'}, format='json')
                return response.status_code
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(pay, range(2))), [200, 201])
        self.assertEqual(FeePayment.objects.filter(student=self.student).count(), 1)
        self.assertEqual(StudentLedgerEntry.objects.filter(student=self.student, kind='payment').count(), 1)
        self.assertEqual(account_balance(self.school, self.student)['outstanding'], Decimal('600.00'))

    def test_distinct_payments_competing_for_charge_do_not_overallocate(self):
        generate_charges(self.school, self.term, self.admin)
        def pay(index):
            close_old_connections()
            try:
                client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
                client.force_authenticate(self.admin)
                response = client.post('/api/fees/pay/manual/', {'student_id': self.student.pk,
                    'fee_schedule_id': self.schedule.pk, 'amount_paid': '700.00',
                    'payment_date': '2026-09-27', 'method': 'cash',
                    'idempotency_key': f'parallel-payment-{index:04d}'}, format='json')
                return response.status_code
            finally: close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(pay, range(2))), [201, 400])
        self.assertEqual(StudentPaymentAllocation.objects.count(), 1)
        self.assertEqual(account_balance(self.school, self.student)['outstanding'], Decimal('300.00'))
