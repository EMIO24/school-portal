from datetime import date, timedelta
from decimal import Decimal
from unittest import skipUnless
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.cache import cache
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from academics.models import AcademicSession, Term
from accounts.models import CustomUser
from enrollment.models import StudentProfile
from tenants.models import PlatformEvent, PlatformSecurity, School
from .billing import active_students
from .invoices import issue_invoice, record_invoice_payment, void_invoice
from .models import PaymentOrder, SubscriptionOffer, TermInvoice


class InvoiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = CustomUser.objects.create_superuser('owner@invoice.test', 'Password!123')
        self.school = School.objects.create(name='Invoice School', slug='invoice', subdomain='invoice',
                                            subscription_plan='premium', approval_status='approved')
        self.other = School.objects.create(name='Other School', slug='other-invoice', subdomain='other-invoice',
                                           subscription_plan='basic')
        self.admin = CustomUser.objects.create_user('admin@invoice.test', 'Password!123',
                                                    school=self.school, role='school_admin', must_change_password=False)
        self.term = self.make_term(self.school, '2026/27')
        self.other_term = self.make_term(self.other, '2026/27')
        self.due = timezone.localdate() + timedelta(days=14)
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.subdomain)
        self.client.force_authenticate(self.admin)

    def make_term(self, school, name):
        session = AcademicSession.objects.create(school=school, name=name,
                                                 start_date=date(2026, 9, 1), end_date=date(2027, 7, 31))
        return Term.objects.create(session=session, name='first', start_date=date(2026, 9, 1),
                                   end_date=date(2026, 12, 31))

    def students(self, count, school=None):
        school = school or self.school
        users = CustomUser.objects.bulk_create([
            CustomUser(school=school, role='student', email=None) for _ in range(count)
        ])
        return StudentProfile.objects.bulk_create([
            StudentProfile(school=school, user=user, admission_number=f'INV-{user.pk}') for user in users
        ])

    def issue(self, school=None, term=None, **kwargs):
        return issue_invoice(school_id=(school or self.school).pk, term_id=(term or self.term).pk,
                             actor=self.owner, due_date=kwargs.pop('due_date', self.due), **kwargs)

    def payment(self, invoice, **kwargs):
        values = dict(school=invoice.school, payer=self.admin, kind='subscription',
                      reference=f'INV-PAY-{PaymentOrder.objects.count()}', mode='test',
                      amount_kobo=int(invoice.final_amount * 100), currency='NGN', payer_email=self.admin.email,
                      plan=invoice.plan, months=3, status='success', paid_at=timezone.now())
        values.update(kwargs)
        return PaymentOrder.objects.create(**values)

    def test_persisted_boundaries_for_all_plans(self):
        students = self.students(500)
        ids = [student.pk for student in students]
        for plan, rate in [('basic', 800), ('premium', 1500), ('enterprise', 2500)]:
            self.school.subscription_plan = plan
            self.school.save()
            for count in [98, 99, 100, 101, 500]:
                with self.subTest(plan=plan, count=count):
                    StudentProfile.objects.filter(school=self.school).update(status='withdrawn')
                    StudentProfile.objects.filter(pk__in=ids[:count]).update(status='active')
                    term = self.make_term(self.school, f'{plan}-{count}')
                    invoice, created = self.issue(term=term)
                    invoice.refresh_from_db()
                    effective = Decimal(rate) * (Decimal('0.9') if count >= 100 else 1)
                    self.assertTrue(created)
                    self.assertEqual(invoice.plan, plan)
                    self.assertEqual(invoice.active_student_count, count)
                    self.assertEqual(invoice.standard_rate, Decimal(rate))
                    self.assertEqual(invoice.discount_applied, count >= 100)
                    self.assertEqual(invoice.discount_percentage, 10 if count >= 100 else 0)
                    self.assertEqual(invoice.effective_rate, effective)
                    self.assertEqual(invoice.subtotal, Decimal(rate) * count)
                    self.assertEqual(invoice.final_amount, effective * count)
                    self.assertEqual(invoice.discount_amount, invoice.subtotal - invoice.final_amount)
        self.assertEqual(TermInvoice.objects.filter(plan='basic', active_student_count=99).get().final_amount, Decimal('79200'))
        self.assertEqual(TermInvoice.objects.filter(plan='basic', active_student_count=100).get().final_amount, Decimal('72000'))
        for plan, expected in [('basic', '360000'), ('premium', '675000'), ('enterprise', '1125000')]:
            self.assertEqual(TermInvoice.objects.get(plan=plan, active_student_count=500).final_amount, Decimal(expected))

    def test_withdrawal_does_not_reprice_history_and_next_term_uses_new_count(self):
        students = self.students(102)
        invoice, _ = self.issue()
        StudentProfile.objects.filter(pk__in=[s.pk for s in students[:3]]).update(status='withdrawn')
        self.assertEqual(active_students(self.school).count(), 99)
        invoice.refresh_from_db()
        self.assertEqual(invoice.active_student_count, 102)
        self.assertEqual(invoice.final_amount, Decimal('137700'))
        next_term = Term.objects.create(session=self.term.session, name='second',
                                        start_date=date(2027, 1, 1), end_date=date(2027, 4, 1))
        next_invoice, _ = self.issue(term=next_term)
        self.assertEqual(next_invoice.active_student_count, 99)
        self.assertEqual(next_invoice.final_amount, Decimal('148500'))
        self.assertNotEqual(next_invoice.invoice_number, invoice.invoice_number)

    def test_repeat_returns_original_after_plan_rate_and_calendar_changes(self):
        self.students(1)
        invoice, _ = self.issue(grace_period_days=5)
        self.school.subscription_plan = 'basic'
        self.school.name = 'Renamed'
        self.school.save()
        SubscriptionOffer.objects.filter(plan='premium').update(amount='9999')
        self.term.session.name = 'Renamed session'
        self.term.session.save()
        again, created = self.issue(due_date=self.due + timedelta(days=20))
        self.assertFalse(created)
        self.assertEqual(again.pk, invoice.pk)
        self.assertEqual(again.school_name, 'Invoice School')
        self.assertEqual(again.session_name, '2026/27')
        self.assertEqual(again.plan, 'premium')
        self.assertEqual(again.final_amount, Decimal('1500'))
        self.assertEqual(again.due_date, self.due)
        self.assertEqual(again.grace_period_days, 5)
        self.assertEqual(PlatformEvent.objects.filter(action='invoice.issued').count(), 1)

    def test_database_rejects_duplicate_period_even_with_different_plan_and_number(self):
        invoice, _ = self.issue()
        fields = {field.attname: getattr(invoice, field.attname) for field in invoice._meta.concrete_fields if not field.primary_key}
        fields.update(invoice_number='PAI-DIFFERENT', plan='basic')
        with self.assertRaises(IntegrityError), transaction.atomic():
            TermInvoice.objects.create(**fields)
        self.assertEqual(TermInvoice.objects.count(), 1)

    def test_immutable_save_queryset_bulk_update_and_delete(self):
        invoice, _ = self.issue()
        invoice.final_amount = Decimal('1')
        attempts = [lambda: invoice.save(), lambda: TermInvoice.objects.filter(pk=invoice.pk).update(final_amount=1),
                    lambda: TermInvoice.objects.bulk_update([invoice], ['final_amount']),
                    lambda: invoice.delete(), lambda: TermInvoice.objects.filter(pk=invoice.pk).delete()]
        for attempt in attempts:
            with self.assertRaises(ModelValidationError):
                attempt()
        invoice.refresh_from_db()
        self.assertEqual(invoice.final_amount, 0)

    def test_snapshot_rounding_preserves_custom_offer(self):
        self.students(101)
        SubscriptionOffer.objects.filter(plan='premium').update(amount='100.05')
        invoice, _ = self.issue()
        invoice.refresh_from_db()
        self.assertEqual(invoice.final_amount, Decimal('9094.54'))
        self.assertEqual(invoice.effective_rate, Decimal('90.0450'))
        self.assertEqual(invoice.subtotal - invoice.discount_amount, invoice.final_amount)

    def test_invalid_due_grace_and_free_plan_do_not_issue(self):
        for kwargs in [{'due_date': timezone.localdate() - timedelta(days=1)}, {'grace_period_days': -1}, {'grace_period_days': 366}]:
            with self.assertRaises(ValidationError):
                self.issue(**kwargs)
        self.school.subscription_plan = 'free'
        self.school.save()
        with self.assertRaises(ValidationError):
            self.issue()
        self.assertFalse(TermInvoice.objects.exists())

    def test_overdue_is_derived_without_changing_snapshot_and_filter_agrees(self):
        invoice, _ = self.issue()
        with patch('django.utils.timezone.localdate', return_value=self.due + timedelta(days=1)):
            self.assertEqual(invoice.display_status, 'overdue')
            response = self.client.get('/api/fees/subscription/invoices/', {'status': 'overdue'})
            self.assertEqual(response.json()['results'][0]['status'], 'overdue')
            self.assertEqual(self.client.get('/api/fees/subscription/invoices/', {'status': 'issued'}).json()['count'], 0)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'issued')

    def test_paid_transition_is_idempotent_and_cannot_be_voided(self):
        self.students(1)
        invoice, _ = self.issue()
        payment = self.payment(invoice)
        for _ in range(2):
            paid = record_invoice_payment(invoice.pk, payment_id=payment.pk)
            self.assertEqual(paid.status, 'paid')
            self.assertEqual(paid.paid_at, payment.paid_at)
        self.assertEqual(PlatformEvent.objects.filter(action='invoice.paid').count(), 1)
        with self.assertRaises(ValidationError):
            void_invoice(invoice.pk, actor=self.owner, reason='Not permitted')

    def test_pending_mismatched_and_historical_payments_cannot_mark_paid(self):
        self.students(1)
        invoice, _ = self.issue()
        for overrides in [{'status': 'pending'}, {'status': 'review'}, {'amount_kobo': 1},
                          {'school': self.other}, {'kind': 'fees'}, {'plan': 'basic'}, {'currency': 'USD'},
                          {'paid_at': invoice.snapshot_at - timedelta(days=1)}]:
            with self.subTest(overrides=overrides):
                payment = self.payment(invoice, **overrides)
                with self.assertRaises(ValidationError):
                    record_invoice_payment(invoice.pk, payment_id=payment.pk)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'issued')

    def test_void_is_terminal_and_duplicate_generation_does_not_replace_it(self):
        invoice, _ = self.issue()
        with self.assertRaises(ValidationError):
            void_invoice(invoice.pk, actor=self.owner, reason=' ')
        void_invoice(invoice.pk, actor=self.owner, reason='Wrong billing period')
        void_invoice(invoice.pk, actor=self.owner, reason='Retry')
        again, created = self.issue()
        self.assertFalse(created)
        self.assertEqual(again.status, 'void')
        self.assertEqual(again.void_reason, 'Wrong billing period')
        self.assertEqual(PlatformEvent.objects.filter(action='invoice.voided').count(), 1)
        with self.assertRaises(ValidationError):
            record_invoice_payment(invoice.pk, payment_id=self.payment(invoice).pk)

    def test_one_verified_payment_cannot_pay_two_invoices(self):
        first, _ = self.issue()
        term = self.make_term(self.school, 'another-session')
        second, _ = self.issue(term=term)
        payment = self.payment(first)
        record_invoice_payment(first.pk, payment_id=payment.pk)
        with self.assertRaises(ValidationError):
            record_invoice_payment(second.pk, payment_id=payment.pk)
        second.refresh_from_db()
        self.assertEqual(second.status, 'issued')

    def test_school_list_detail_and_mutation_cannot_leak_other_school(self):
        own, _ = self.issue()
        foreign, _ = self.issue(school=self.other, term=self.other_term)
        root = '/api/fees/subscription/invoices/'
        response = self.client.get(root)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(response.json()['results'][0]['id'], own.pk)
        self.assertIsInstance(response.json()['results'][0]['final_amount'], str)
        self.assertEqual(self.client.get(f'{root}{foreign.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'{root}999999/').json(), self.client.get(f'{root}{foreign.pk}/').json())
        self.assertEqual(self.client.get(root, {'school': self.other.pk}).status_code, 400)
        self.assertEqual(self.client.get(root, {'term': self.other_term.pk}).json()['count'], 0)
        self.assertEqual(self.client.get(root, HTTP_X_SCHOOL_SLUG=self.other.subdomain).status_code, 403)
        for method in ['post', 'patch', 'put', 'delete']:
            self.assertEqual(getattr(self.client, method)(f'{root}{foreign.pk}/', {}, format='json').status_code, 405)
        self.assertEqual(self.client.post('/api/platform/invoices/', {}).status_code, 403)
        self.assertEqual(self.client.post(f'/api/platform/invoices/{foreign.pk}/', {'action': 'void', 'reason': 'attack'}).status_code, 403)

    def test_owner_generation_filters_and_void_actions(self):
        self.client.force_authenticate(self.owner)
        root = '/api/platform/invoices/'
        payload = {'school': self.school.pk, 'term': self.term.pk, 'due_date': str(self.due), 'grace_period_days': 7}
        first = self.client.post(root, payload, format='json')
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(self.client.post(root, payload, format='json').status_code, 200)
        self.issue(school=self.other, term=self.other_term)
        self.assertEqual(self.client.get(root).json()['count'], 2)
        filters = {'school': self.school.pk, 'plan': 'premium', 'academic_session': self.term.session_id,
                   'term': self.term.pk, 'status': 'issued'}
        self.assertEqual(self.client.get(root, filters).json()['count'], 1)
        self.assertEqual(self.client.get(root, {'status': 'bogus'}).status_code, 400)
        self.assertEqual(self.client.post(root, {**payload, 'final_amount': '1'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(root, {**payload, 'term': self.other_term.pk}, format='json').status_code, 404)
        detail = f"{root}{first.data['id']}/"
        self.assertEqual(self.client.post(detail, {'action': 'paid'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(detail, {'status': 'paid'}, format='json').status_code, 405)
        self.assertEqual(self.client.post(detail, {'action': 'void', 'reason': 'Correction'}, format='json').status_code, 200)
        self.assertEqual(self.client.get(root, {'status': 'void'}).json()['count'], 1)

    def test_anonymous_teachers_parents_students_and_platform_viewer_are_denied(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/fees/subscription/invoices/').status_code, 401)
        for role in ['teacher', 'parent', 'student']:
            user = CustomUser.objects.create_user(f'{role}@invoice.test', 'Password!123', school=self.school,
                                                  role=role, must_change_password=False)
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get('/api/fees/subscription/invoices/').status_code, 403)
            self.assertEqual(self.client.get('/api/platform/invoices/').status_code, 403)
        PlatformSecurity.objects.create(user=self.owner, access_level='viewer')
        self.owner.refresh_from_db()
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/platform/invoices/').status_code, 403)


@skipUnless(connection.vendor == 'postgresql', 'Concurrent row-lock test requires disposable PostgreSQL test database.')
class InvoiceConcurrencyTests(TransactionTestCase):
    def test_simultaneous_generation_returns_one_invoice(self):
        owner = CustomUser.objects.create_superuser('concurrent@invoice.test', 'Password!123')
        school = School.objects.create(name='Concurrent', slug='concurrent', subdomain='concurrent', subscription_plan='basic')
        session = AcademicSession.objects.create(school=school, name='2026/27', start_date=date(2026, 9, 1), end_date=date(2027, 7, 31))
        term = Term.objects.create(session=session, name='first', start_date=date(2026, 9, 1), end_date=date(2026, 12, 31))
        SubscriptionOffer.objects.get_or_create(plan='basic', defaults={'amount': '800', 'months': 3, 'enabled': True})
        barrier = Barrier(2)

        def generate():
            try:
                barrier.wait(timeout=10)
                return issue_invoice(school_id=school.pk, term_id=term.pk, actor=owner,
                                     due_date=timezone.localdate())[0].pk
            finally:
                connections['default'].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(generate) for _ in range(2)]
            ids = [future.result(timeout=20) for future in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(TermInvoice.objects.count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action='invoice.issued').count(), 1)
