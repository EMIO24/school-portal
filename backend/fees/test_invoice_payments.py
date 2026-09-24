import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from unittest import skipUnless
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import IntegrityError, connection, connections, transaction
from django.template.loader import render_to_string
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from tenants.models import PlatformEvent
from . import test_invoices
from .invoice_payments import amount_in_kobo
from .invoices import void_invoice
from .models import FeePayment, PaymentOrder, SubscriptionOffer, TermInvoice
from .payments import add_months, settle
from .services.paystack import PaystackService


@override_settings(PAYSTACK_SECRET_KEY='sk_test_fixture', PAYSTACK_MODE='test', FRONTEND_URL='http://localhost:3001')
class InvoicePaymentTests(TestCase):
    setUp = test_invoices.InvoiceTests.setUp
    make_term = test_invoices.InvoiceTests.make_term
    students = test_invoices.InvoiceTests.students
    issue = test_invoices.InvoiceTests.issue

    def invoice(self, count=1):
        self.students(count)
        return self.issue()[0]

    def checkout(self, invoice, **extra):
        with patch.object(PaystackService, 'initialize', return_value=('https://checkout.paystack.com/test', 'test')):
            return self.client.post('/api/fees/subscription/', {'invoice_id': invoice.pk, **extra}, format='json')

    def verified(self, order, **overrides):
        return {'status': 'success', 'reference': order.reference, 'amount': order.amount_kobo,
                'currency': 'NGN', 'domain': 'test', 'customer': {'email': order.payer_email}, 'id': 7, **overrides}

    def test_checkout_uses_immutable_amount_and_duration_after_changes(self):
        invoice = self.invoice(102)
        from enrollment.models import StudentProfile
        ids = list(StudentProfile.objects.filter(school=self.school).values_list('id', flat=True)[:3])
        StudentProfile.objects.filter(pk__in=ids).update(status='withdrawn')
        SubscriptionOffer.objects.filter(plan='premium').update(amount='9999', months=12)
        self.assertEqual(self.checkout(invoice).status_code, 200)
        order = PaymentOrder.objects.get()
        self.assertEqual(order.amount_kobo, 13770000)
        self.assertEqual(order.months, 3)
        self.assertEqual(order.invoice_id, invoice.pk)
        settle(order.reference, self.verified(order))
        self.school.refresh_from_db()
        self.assertEqual(self.school.subscription_ends_on, add_months(timezone.localdate(), 3))
        self.assertFalse(FeePayment.objects.exists())

    def test_frontend_amount_status_and_plan_tampering_rejected(self):
        invoice = self.invoice()
        for extra in [{'amount': '1'}, {'status': 'paid'}, {'plan': 'basic'}]:
            self.assertEqual(self.checkout(invoice, **extra).status_code, 400)
        self.assertFalse(PaymentOrder.objects.exists())

    def test_duplicate_pending_checkout_reuses_reference(self):
        invoice = self.invoice()
        first = self.checkout(invoice)
        order = PaymentOrder.objects.get()
        with patch.object(PaystackService, 'verify', return_value=self.verified(order, status='pending')):
            second = self.checkout(invoice)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['reference'], second.data['reference'])
        self.assertEqual(PaymentOrder.objects.count(), 1)

    def test_failed_and_abandoned_attempts_allow_unpaid_retry(self):
        invoice = self.invoice()
        self.checkout(invoice)
        for state in ['failed', 'abandoned']:
            order = PaymentOrder.objects.latest('id')
            with patch.object(PaystackService, 'verify', return_value=self.verified(order, status=state)):
                self.assertEqual(self.checkout(invoice).status_code, 200)
            order.refresh_from_db()
            self.assertEqual(order.status, 'failed')
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'issued')

    def test_duplicate_verification_and_webhooks_settle_once(self):
        invoice = self.invoice()
        self.checkout(invoice)
        order = PaymentOrder.objects.get()
        body = json.dumps({'event':'charge.success', 'data':{'reference': order.reference}})
        signature = hmac.new(b'sk_test_fixture', body.encode(), hashlib.sha512).hexdigest()
        with patch.object(PaystackService, 'verify', return_value=self.verified(order)):
            for _ in range(2):
                self.assertEqual(self.client.get('/api/fees/pay/verify/', {'reference':order.reference}).data['status'], 'success')
                self.assertEqual(self.client.post('/api/platform/paystack/webhook/', body, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=signature).status_code, 200)
        invoice.refresh_from_db(); self.school.refresh_from_db()
        self.assertEqual(invoice.payment_id, order.pk)
        self.assertEqual(invoice.status, 'paid')
        self.assertEqual(self.school.subscription_ends_on, add_months(timezone.localdate(), 3))
        self.assertEqual(PlatformEvent.objects.filter(action='invoice.paid').count(), 1)
        self.assertEqual(self.checkout(invoice).status_code, 400)

    def test_invalid_signature_and_reference_apply_no_credit(self):
        invoice = self.invoice(); self.checkout(invoice); order = PaymentOrder.objects.get()
        self.assertEqual(self.client.post('/api/platform/paystack/webhook/', {}, format='json', HTTP_X_PAYSTACK_SIGNATURE='invalid').status_code, 403)
        settled = settle(order.reference, self.verified(order, reference='wrong-reference'))
        self.assertEqual(settled.status, 'review')
        invoice.refresh_from_db(); self.assertEqual(invoice.status, 'issued')

    def test_lower_higher_and_currency_mismatch_require_review(self):
        invoice = self.invoice(); self.checkout(invoice); order = PaymentOrder.objects.get()
        for changes in [{'amount': order.amount_kobo - 1}, {'amount': order.amount_kobo + 1}, {'currency': 'USD'}]:
            settled = settle(order.reference, self.verified(order, **changes))
            self.assertEqual(settled.status, 'review')
            invoice.refresh_from_db(); self.assertEqual(invoice.status, 'issued')
        self.assertEqual(self.checkout(invoice).status_code, 409)

    def test_wrong_invoice_or_school_association_requires_review(self):
        invoice = self.invoice(); self.checkout(invoice); order = PaymentOrder.objects.get()
        another, _ = self.issue(term=self.make_term(self.school, 'Other term'))
        PaymentOrder.objects.filter(pk=order.pk).update(invoice=another)
        self.assertEqual(settle(order.reference, self.verified(order)).status, 'review')
        PaymentOrder.objects.filter(pk=order.pk).update(invoice=invoice, school=self.other)
        self.assertEqual(settle(order.reference, self.verified(order)).status, 'review')
        self.assertEqual(TermInvoice.objects.filter(status='paid').count(), 0)

    def test_void_and_zero_amount_invoices_cannot_be_paid(self):
        invoice = self.invoice()
        void_invoice(invoice.pk, actor=self.owner, reason='Incorrect period')
        self.assertEqual(self.checkout(invoice).status_code, 400)
        empty, _ = self.issue(school=self.other, term=self.other_term)
        self.assertEqual(empty.final_amount, 0)
        for value in [Decimal('0'), Decimal('-1'), Decimal('1.001')]:
            with self.assertRaises(ValidationError): amount_in_kobo(value)
        self.assertEqual(amount_in_kobo(Decimal('9094.54')), 909454)

    def test_unfinished_attempt_blocks_void_and_double_open_database_insert(self):
        invoice = self.invoice(); self.checkout(invoice); order = PaymentOrder.objects.get()
        with self.assertRaises(ValidationError): void_invoice(invoice.pk, actor=self.owner, reason='Not yet')
        values = {f.attname:getattr(order,f.attname) for f in order._meta.concrete_fields if not f.primary_key}
        values['reference'] = 'another-reference'
        with self.assertRaises(IntegrityError), transaction.atomic(): PaymentOrder.objects.create(**values)

    def test_cross_tenant_checkout_receipts_details_verification_and_owner_actions_denied(self):
        foreign, _ = self.issue(school=self.other, term=self.other_term)
        self.assertEqual(self.checkout(foreign).status_code, 404)
        for suffix in ['', 'invoice.pdf', 'receipt.pdf']:
            self.assertEqual(self.client.get(f'/api/fees/subscription/invoices/{foreign.pk}/' + suffix).status_code, 404)
        foreign_order = PaymentOrder.objects.create(invoice=foreign, school=self.other, payer=self.admin, kind='subscription',
            amount_kobo=100, reference='foreign-ref', mode='test', payer_email=self.admin.email)
        self.assertEqual(self.client.get('/api/fees/pay/verify/', {'reference':foreign_order.reference}).status_code, 404)
        self.assertEqual(self.client.post('/api/platform/payments/', {'reference':foreign_order.reference}).status_code, 403)
        self.assertEqual(self.client.get(f'/api/platform/invoices/{foreign.pk}/receipt.pdf').status_code, 403)

    def test_pdf_and_receipt_use_snapshot_and_one_receipt_identity(self):
        invoice = self.invoice(); root = f'/api/fees/subscription/invoices/{invoice.pk}/'
        self.assertEqual(self.client.get(root + 'receipt.pdf').status_code, 400)
        self.checkout(invoice); order = PaymentOrder.objects.get(); settle(order.reference, self.verified(order))
        self.school.name = 'Changed school'; self.school.save()
        detail = self.client.get(root).json()
        self.assertEqual(detail['school_name'], 'Invoice School')
        self.assertEqual(detail['receipt_number'], 'RCP-' + invoice.invoice_number)
        for document in ['invoice.pdf', 'receipt.pdf']:
            response = self.client.get(root + document)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.content.startswith(b'%PDF'))
            self.assertIn('no-store', response['Cache-Control'])
        invoice.refresh_from_db()
        html = render_to_string('fees/subscription_invoice.html', {'invoice':invoice, 'receipt':True, 'number':detail['receipt_number']})
        self.assertIn('Invoice School', html); self.assertNotIn('Changed school', html)
        self.assertIn(order.reference, html)
        self.assertEqual(self.client.get(root).json()['receipt_number'], detail['receipt_number'])

    def test_legacy_duration_requires_explicit_owner_assignment_once(self):
        invoice = self.invoice()
        from django.db.models import QuerySet
        QuerySet.update(TermInvoice.objects.filter(pk=invoice.pk), subscription_months=None)
        self.assertEqual(self.checkout(invoice).status_code, 400)
        url = f'/api/platform/invoices/{invoice.pk}/'
        self.assertEqual(self.client.post(url, {'action':'set_duration','months':3}).status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post(url, {'action':'set_duration','months':3}).status_code, 200)
        self.assertEqual(self.client.post(url, {'action':'set_duration','months':6}).status_code, 400)

    def test_legacy_unlinked_success_still_verifies_without_invoice(self):
        order = PaymentOrder.objects.create(school=self.school,payer=self.admin,payer_email=self.admin.email,
            kind='subscription',plan='premium',months=3,amount_kobo=150000,mode='test',reference='legacy-ref')
        settle(order.reference,self.verified(order))
        self.school.refresh_from_db()
        self.assertEqual(self.school.subscription_ends_on, add_months(timezone.localdate(),3))
        self.assertFalse(TermInvoice.objects.exists())


@skipUnless(connection.vendor == 'postgresql', 'PRE-PROMOTION POSTGRESQL TEST REQUIRED')
@override_settings(PAYSTACK_MODE='test')
class InvoiceSettlementConcurrencyTests(TransactionTestCase):
    def test_verification_and_webhook_settlement_race_has_one_effect(self):
        from accounts.models import CustomUser
        from tenants.models import School
        from academics.models import AcademicSession, Term
        from enrollment.models import StudentProfile
        from .invoices import issue_invoice
        owner = CustomUser.objects.create_superuser('race@invoice.test', 'Password!123')
        school = School.objects.create(name='Race', slug='race', subdomain='race', subscription_plan='premium')
        student = CustomUser.objects.create_user(None, 'Password!123', school=school, role='student')
        StudentProfile.objects.create(school=school, user=student)
        session = AcademicSession.objects.create(school=school, name='2026/27', start_date='2026-09-01', end_date='2027-07-31')
        term = Term.objects.create(session=session, name='first', start_date='2026-09-01', end_date='2026-12-31')
        SubscriptionOffer.objects.get_or_create(plan='premium', defaults={'amount':'1500','months':3,'enabled':True})
        invoice, _ = issue_invoice(school_id=school.pk, term_id=term.pk, actor=owner, due_date=timezone.localdate())
        order = PaymentOrder.objects.create(invoice=invoice, school=school, payer=owner, payer_email=owner.email,
            reference=f'SCH-I{invoice.pk}-race', kind='subscription', plan='premium', months=3, amount_kobo=150000,
            mode='test', status='pending')
        data = {'status':'success','reference':order.reference,'amount':150000,'currency':'NGN','domain':'test',
                'customer':{'email':owner.email},'id':1}
        barrier = Barrier(2)

        def reconcile():
            try:
                barrier.wait(timeout=10)
                return settle(order.reference, data).status
            finally:
                connections['default'].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(reconcile) for _ in range(2)]
            self.assertEqual([f.result(timeout=20) for f in futures], ['success', 'success'])
        invoice.refresh_from_db(); school.refresh_from_db()
        self.assertEqual(invoice.payment_id, order.pk)
        self.assertEqual(school.subscription_ends_on, add_months(timezone.localdate(), 3))
        self.assertEqual(PlatformEvent.objects.filter(action='invoice.paid').count(), 1)
        self.assertFalse(FeePayment.objects.exists())
