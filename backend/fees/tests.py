import hashlib
import hmac
import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.core.cache import cache
from requests.exceptions import Timeout
from rest_framework.test import APIClient
from accounts.models import CustomUser, ParentStudentLink
from tenants.models import School, PlatformSecurity
from enrollment.models import StudentProfile, ClassLevel, ClassArm
from academics.models import AcademicSession, Term
from .models import FeeCategory, FeeSchedule, FeePayment, SchoolPaymentAccount, PaymentOrder, SubscriptionOffer, TermInvoice
from .payments import settle, add_months
from .services.paystack import PaystackService


@override_settings(PAYSTACK_SECRET_KEY='sk_test_fixture', PAYSTACK_MODE='test', FRONTEND_URL='http://localhost:3001')
class PaystackTests(TestCase):
    def setUp(self):
        cache.clear()
        self.school = School.objects.create(name='Payment school', slug='pay', subdomain='pay', subscription_plan='basic')
        self.other = School.objects.create(name='Other', slug='other', subdomain='other')
        self.admin = CustomUser.objects.create_user('admin@pay.test', 'Password!123', school=self.school, role='school_admin')
        self.user = CustomUser.objects.create_user('student@pay.test', 'Password!123', school=self.school, role='student')
        self.owner = CustomUser.objects.create_superuser('owner@pay.test', 'Password!123')
        level = ClassLevel.objects.create(school=self.school, name='JSS1', order_index=1)
        arm = ClassArm.objects.create(school=self.school, class_level=level, name='A')
        self.student = StudentProfile.objects.create(school=self.school, user=self.user, current_class=arm, admission_number='PAY001')
        session = AcademicSession.objects.create(school=self.school, name='2026/27', start_date='2026-09-01', end_date='2027-07-31')
        term = Term.objects.create(session=session, name='first', start_date='2026-09-01', end_date='2026-12-31')
        cat = FeeCategory.objects.create(school=self.school, name='Tuition')
        self.fee = FeeSchedule.objects.create(school=self.school, term=term, class_level=level, fee_category=cat, amount=10000)
        self.account = SchoolPaymentAccount.objects.create(school=self.school, mode='test', subaccount_code='ACCT_school', business_name='School')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.headers = {'HTTP_X_SCHOOL_SLUG':'pay'}
    def start(self):
        with patch.object(PaystackService, 'initialize', side_effect=lambda email, amount, ref, callback, **kw: ('https://checkout.paystack.com/test', ref)):
            return self.client.post('/api/fees/pay/initiate/', {'student_id': self.student.pk, 'fee_schedule_ids':[self.fee.pk]}, format='json', **self.headers)
    def data(self, order, **overrides):
        return {'status':'success', 'reference':order.reference, 'amount':order.amount_kobo, 'currency':'NGN', 'domain':'test', 'customer':{'email':order.payer_email}, 'id':123, **overrides}
    def test_outstanding_only_and_idempotent_receipts(self):
        FeePayment.objects.create(school=self.school, student=self.student, fee_schedule=self.fee, amount_paid=2500, payment_date=date.today(), method='cash')
        self.assertEqual(self.start().status_code,200)
        order = PaymentOrder.objects.get()
        self.assertEqual(order.amount_kobo,750000)
        self.assertEqual(order.subaccount_code,'ACCT_school')
        settle(order.reference,self.data(order)); settle(order.reference,self.data(order))
        self.assertEqual(FeePayment.objects.filter(paystack_reference=order.reference).count(),1)
        self.assertEqual(self.start().status_code,400)
    def test_pending_checkout_blocks_duplicate(self):
        self.start()
        self.assertEqual(self.start().status_code,409)
        self.assertEqual(PaymentOrder.objects.count(),1)
    def test_unmatched_amount_currency_email_reference_or_mode_never_credits(self):
        self.start(); order = PaymentOrder.objects.get()
        for changes in [{'amount':1}, {'currency':'USD'}, {'domain':'live'}, {'reference':'other'}, {'customer':{'email':'stranger@example.test'}}, {'amount':True}]:
            settle(order.reference,self.data(order,**changes))
            self.assertFalse(FeePayment.objects.exists())
        order.refresh_from_db(); self.assertEqual(order.status,'review')
    def test_missing_school_account_does_not_route_fees_to_platform(self):
        self.account.delete()
        self.assertEqual(self.start().status_code,409)
        self.assertFalse(PaymentOrder.objects.exists())
    def test_network_timeout_preserves_order_for_reconciliation(self):
        with patch.object(PaystackService,'initialize',side_effect=Timeout):
            r=self.client.post('/api/fees/pay/initiate/',{'student_id':self.student.pk,'fee_schedule_ids':[self.fee.pk]},format='json',**self.headers)
        self.assertEqual(r.status_code,502)
        order=PaymentOrder.objects.get(); self.assertEqual(r.data['reference'],order.reference)
        with patch.object(PaystackService,'verify',side_effect=Timeout):
            r=self.client.get('/api/fees/pay/verify/',{'reference':order.reference},**self.headers)
        self.assertEqual(r.status_code,502); self.assertFalse(FeePayment.objects.exists())
    def test_cross_school_and_unlinked_parent_denied(self):
        self.assertEqual(self.client.get('/api/fees/student/%s/'%self.student.pk,HTTP_X_SCHOOL_SLUG='other').status_code,403)
        parent=CustomUser.objects.create_user('parent@pay.test','Password!123',school=self.school,role='parent')
        self.client.force_authenticate(parent)
        self.assertEqual(self.start().status_code,403)
        ParentStudentLink.objects.create(school=self.school,parent=parent,student=self.student)
        self.assertEqual(self.start().status_code,200)
    def test_student_cannot_record_manual_payments_or_edit_offers(self):
        self.assertEqual(self.client.post('/api/fees/pay/manual/',{},format='json',**self.headers).status_code,403)
        self.assertEqual(self.client.post('/api/platform/payments/',{},format='json').status_code,403)
    def test_webhook_signature_and_duplicate_delivery(self):
        self.start(); order=PaymentOrder.objects.get()
        body=json.dumps({'event':'charge.success','data':{'reference':order.reference}})
        url='/api/platform/paystack/webhook/'
        self.client.force_authenticate(None)
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,403)
        signature=hmac.new(b'sk_test_fixture',body.encode(),hashlib.sha512).hexdigest()
        with patch.object(PaystackService,'verify',return_value=self.data(order)):
            for _ in range(2):
                self.assertEqual(self.client.post(url,body,content_type='application/json',HTTP_X_PAYSTACK_SIGNATURE=signature).status_code,200)
        self.assertEqual(FeePayment.objects.count(),1)
    def test_subscription_extends_once_and_never_unsuspends(self):
        self.client.force_authenticate(self.admin)
        with patch.object(PaystackService,'initialize',side_effect=lambda email,amount,ref,callback,**kw:('https://checkout.paystack.com/test',ref)):
            r=self.client.post('/api/fees/subscription/',{'plan':'basic'},format='json',**self.headers)
        self.assertEqual(r.status_code,200,r.data)
        order=PaymentOrder.objects.get();self.assertEqual(order.amount_kobo,80000);self.assertFalse(order.subaccount_code)
        self.school.is_active=False;self.school.save()
        settle(order.reference,self.data(order));self.school.refresh_from_db(); end=self.school.subscription_ends_on
        settle(order.reference,self.data(order));self.school.refresh_from_db()
        self.assertEqual(end,self.school.subscription_ends_on);self.assertFalse(self.school.is_active)
        self.assertEqual(self.school.subscription_plan,'basic')
    def test_subscription_10_percent_discount_for_100_students_and_above(self):
        self.client.force_authenticate(self.admin)
        for index in range(99):
            user = CustomUser.objects.create_user(f'bulk{index}@pay.test', 'Password!123', school=self.school, role='student')
            StudentProfile.objects.create(school=self.school, user=user, current_class=None, admission_number=f'BULK{index:03d}')
        with patch.object(PaystackService,'initialize',side_effect=lambda email,amount,ref,callback,**kw:('https://checkout.paystack.com/test',ref)):
            r=self.client.post('/api/fees/subscription/',{'plan':'basic'},format='json',**self.headers)
        self.assertEqual(r.status_code,200,r.data)
        order=PaymentOrder.objects.get(); self.assertEqual(order.amount_kobo,7200000)
    def test_term_invoice_records_audit_trail_for_subscription_billing(self):
        session = AcademicSession.objects.create(school=self.school, name='2026/2027', start_date='2026-09-01', end_date='2027-07-31', is_current=True)
        term = Term.objects.create(session=session, name='first', start_date='2026-09-01', end_date='2026-12-31', is_current=True)
        for index in range(418):
            user = CustomUser.objects.create_user(f'invoice{index}@pay.test', 'Password!123', school=self.school, role='student')
            StudentProfile.objects.create(school=self.school, user=user, current_class=None, admission_number=f'INV{index:03d}')
        invoice = TermInvoice.objects.create(
            school=self.school,
            plan='premium',
            academic_session=session,
            term=term,
            active_student_count=418,
            snapshot_date=date(2026, 9, 20),
            standard_rate=Decimal('1500.00'),
            discount_eligible=True,
            discount_percentage=10,
            discount_amount=Decimal('56430.00'),
            effective_rate=Decimal('1350.00'),
            subtotal=Decimal('627000.00'),
            final_amount=Decimal('564300.00'),
            invoice_number='INV-2026-001',
            issue_date=date(2026, 9, 20),
            due_date=date(2026, 10, 4),
            status='issued',
            grace_period_days=14,
            notes='Premium plan rate with 10% discount for 418 active students.'
        )
        self.assertEqual(invoice.plan, 'premium')
        self.assertEqual(invoice.active_student_count, 418)
        self.assertEqual(invoice.discount_percentage, 10)
        self.assertEqual(invoice.effective_rate, Decimal('1350.00'))
        self.assertEqual(invoice.final_amount, Decimal('564300.00'))
        self.assertIn('10%', invoice.notes)

    def test_term_invoice_is_immutable_after_generation(self):
        from fees.payments import create_term_invoice_for_payment

        session = AcademicSession.objects.create(school=self.school, name='2026/2027', start_date='2026-09-01', end_date='2027-07-31', is_current=True)
        term = Term.objects.create(session=session, name='first', start_date='2026-09-01', end_date='2026-12-31', is_current=True)

        for index in range(102):
            user = CustomUser.objects.create_user(f'freeze{index}@pay.test', 'Password!123', school=self.school, role='student')
            StudentProfile.objects.create(school=self.school, user=user, current_class=None, admission_number=f'FRZ{index:03d}')

        invoice = create_term_invoice_for_payment(
            school=self.school,
            plan_code='premium',
            academic_session=session,
            term=term,
            active_student_count=102,
            issued_on=date(2026, 9, 20),
            due_date=date(2026, 10, 4),
            notes='Initial snapshot for term billing.'
        )
        self.assertEqual(invoice.final_amount, Decimal('137700.00'))

        for index in range(102, 99, -1):
            student = StudentProfile.objects.filter(school=self.school, user__email=f'freeze{index-1}@pay.test').first()
            if student:
                student.delete()

        regenerated = create_term_invoice_for_payment(
            school=self.school,
            plan_code='premium',
            academic_session=session,
            term=term,
            active_student_count=99,
            issued_on=date(2026, 9, 21),
            due_date=date(2026, 10, 5),
            notes='Late recalculation attempt.'
        )

        self.assertEqual(regenerated.pk, invoice.pk)
        regenerated.refresh_from_db()
        self.assertEqual(regenerated.active_student_count, 102)
        self.assertEqual(regenerated.final_amount, Decimal('137700.00'))
        self.assertEqual(regenerated.audit_snapshot['active_student_count'], 102)

    def test_owner_controls_work_without_tenant_and_viewer_denied(self):
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get('/api/platform/payments/').status_code,200)
        r=self.client.post('/api/platform/payments/',{'plan':'basic','amount':'80000','months':3,'enabled':True},format='json')
        self.assertEqual(r.status_code,200)
        PlatformSecurity.objects.create(user=self.owner,access_level='viewer')
        self.assertEqual(self.client.post('/api/platform/payments/',{},format='json').status_code,403)
    def test_subaccount_is_verified_and_cannot_be_shared(self):
        self.client.force_authenticate(self.owner)
        data={'subaccount_code':'ACCT_school','business_name':'School','active':True,'currency':'NGN','domain':'test','account_number':'0123456789','settlement_bank':'Test Bank'}
        with patch.object(PaystackService,'subaccount',return_value=data):
            r=self.client.post('/api/platform/schools/%s/payments/'%self.other.pk,{'subaccount_code':'ACCT_school'},format='json')
        self.assertEqual(r.status_code,400)
    def test_calendar_month_end(self):
        self.assertEqual(add_months(date(2026,1,31),1),date(2026,2,28))
    def test_initialize_splits_school_settlement_without_platform_commission(self):
        from unittest.mock import Mock
        response=Mock(status_code=200)
        response.json.return_value={'status':True,'data':{'authorization_url':'https://checkout.paystack.com/test','reference':'ref'}}
        with patch('fees.services.paystack.requests.post',return_value=response) as post:
            PaystackService().initialize('payer@test.com',10000,'ref','http://localhost:3001/payments/return',subaccount='ACCT_school')
        payload=post.call_args.kwargs['json']
        self.assertEqual(payload['subaccount'],'ACCT_school');self.assertEqual(payload['transaction_charge'],0);self.assertEqual(payload['bearer'],'subaccount')

    def test_payment_details_do_not_leak_to_other_users(self):
        self.start(); order = PaymentOrder.objects.get()
        stranger = CustomUser.objects.create_user('stranger@pay.test', 'Password!123', school=self.school, role='student')
        self.client.force_authenticate(stranger)
        self.assertEqual(self.client.get('/api/fees/pay/verify/', {'reference': order.reference}, **self.headers).status_code, 403)
        settle(order.reference, self.data(order))
        receipt = FeePayment.objects.get()
        self.assertEqual(self.client.get('/api/fees/receipts/%s/' % receipt.pk, **self.headers).status_code, 403)
    def test_manual_payment_invalid_calendar_date_returns_400(self):
        self.client.force_authenticate(self.admin)
        payload = {'student_id': self.student.pk, 'fee_schedule_id': self.fee.pk, 'amount_paid': 500, 'payment_date': '2026-02-30', 'method': 'cash'}
        response = self.client.post('/api/fees/pay/manual/', payload, format='json', **self.headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn('payment_date', response.data['error'])
    def test_manual_payment_cannot_fake_paystack_or_exceed_balance(self):
        self.client.force_authenticate(self.admin)
        payload = {'student_id': self.student.pk, 'fee_schedule_id': self.fee.pk, 'amount_paid': 500, 'payment_date': '2026-09-15', 'method': 'paystack'}
        self.assertEqual(self.client.post('/api/fees/pay/manual/', payload, format='json', **self.headers).status_code, 400)
        payload.update(method='cash', amount_paid=20000)
        self.assertEqual(self.client.post('/api/fees/pay/manual/', payload, format='json', **self.headers).status_code, 400)
    def test_balance_change_requires_review_instead_of_double_credit(self):
        self.start(); order = PaymentOrder.objects.get()
        FeePayment.objects.create(school=self.school, student=self.student, fee_schedule=self.fee, amount_paid=10000, payment_date=date.today(), method='cash')
        settled = settle(order.reference, self.data(order))
        self.assertEqual(settled.status, 'review')
        self.assertEqual(FeePayment.objects.count(), 1)
    def test_verified_failed_payment_allows_new_checkout(self):
        self.start(); order = PaymentOrder.objects.get()
        settle(order.reference, self.data(order, status='failed'))
        self.assertEqual(self.start().status_code, 200)

