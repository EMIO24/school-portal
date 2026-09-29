from decimal import Decimal
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import CustomUser
from enrollment.models import StudentProfile
from tenants.models import School
from .billing import active_students, subscription_quote
from .models import PaymentOrder, SubscriptionOffer
from .payments import settle
from .services.paystack import PaystackService


class BillingCalculationTests(SimpleTestCase):
    def test_all_plan_boundaries(self):
        for plan, rate in [('basic', 800), ('premium', 1500), ('enterprise', 2500)]:
            for count in [98, 99, 100, 101, 500]:
                with self.subTest(plan=plan, count=count):
                    quote = subscription_quote(count, rate)
                    discounted = count >= 100
                    effective = Decimal(rate) * (Decimal('0.9') if discounted else 1)
                    self.assertEqual(quote['standard_rate'], Decimal(rate))
                    self.assertEqual(quote['effective_rate'], effective)
                    self.assertEqual(quote['discount_percent'], 10 if discounted else 0)
                    self.assertEqual(quote['total_amount'], effective * count)
                    self.assertEqual(quote['discount_amount'], Decimal(rate) * count - effective * count)

    def test_invalid_counts_and_rates_rejected(self):
        for count in [-1, 1.5, True, '100']:
            with self.assertRaises(ValueError):
                subscription_quote(count, 800)
        for rate in ['-1', 'NaN', 'Infinity', '1.001']:
            with self.assertRaises(ValueError):
                subscription_quote(1, rate)

    def test_zero_students_and_existing_custom_rate(self):
        self.assertEqual(subscription_quote(0, '1750.25')['total_amount'], Decimal('0'))
        self.assertEqual(subscription_quote(100, '1750.25')['total_amount'], Decimal('157522.50'))

    def test_fractional_discount_preserves_checkout_rounding(self):
        quote = subscription_quote(101, '100.05')
        self.assertEqual(quote['total_amount'], Decimal('9094.54'))
        self.assertEqual(quote['subtotal'] - quote['discount_amount'], quote['total_amount'])


@override_settings(PAYSTACK_MODE='test', PAYSTACK_SECRET_KEY='sk_test_fixture', FRONTEND_URL='http://localhost:3001')
class EnterpriseSubscriptionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.school = School.objects.create(name='Billing School', slug='billing', subdomain='billing',
                                            subscription_plan='enterprise', approval_status='approved')
        self.other = School.objects.create(name='Other', slug='billing-other', subdomain='billing-other')
        self.admin = CustomUser.objects.create_user('admin@billing.test', 'Password!123',
                                                    school=self.school, role='school_admin', must_change_password=False)
        self.owner = CustomUser.objects.create_superuser('owner@billing.test', 'Password!123')
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.subdomain)
        self.client.force_authenticate(self.admin)

    def student(self, school, status='active', login_active=True):
        user = CustomUser.objects.create_user(None, 'Password!123', school=school,
                                             role='student', is_active=login_active)
        return StudentProfile.objects.create(user=user, school=school, status=status)

    def test_enrollment_state_and_tenant_define_billable_students(self):
        self.student(self.school)
        self.student(self.school, login_active=False)
        self.student(self.school, 'withdrawn')
        self.student(self.school, 'graduated')
        self.student(self.other)
        self.assertEqual(active_students(self.school).count(), 2)

    def test_owner_can_assign_enterprise_and_admin_cannot(self):
        url = f'/api/platform/schools/{self.school.pk}/'
        self.assertEqual(self.client.patch(url, {'subscription_plan': 'enterprise'}).status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(url, {'subscription_plan': 'enterprise'}).status_code, 200)

    def test_enterprise_inherits_premium_without_cross_tenant_access(self):
        self.assertEqual(self.client.get('/api/cbt/topics/').status_code, 200)
        self.other.subscription_plan = 'enterprise'
        self.other.save()
        self.assertEqual(self.client.get('/api/cbt/topics/', HTTP_X_SCHOOL_SLUG=self.other.subdomain).status_code, 403)

    def test_quote_checkout_and_repeated_settlement_agree(self):
        self.student(self.school)
        data = self.client.get('/api/fees/subscription/').json()
        offer = next(o for o in data['offers'] if o['plan'] == 'enterprise')
        self.assertEqual(offer['amount'], 2500)
        self.assertEqual(offer['total_amount'], 2500)
        with patch.object(PaystackService, 'initialize', return_value=('https://checkout.paystack.com/test', 'test')):
            from academics.models import AcademicSession, Term
            from django.utils import timezone
            from .invoices import issue_invoice
            session = AcademicSession.objects.create(school=self.school, name='2026/27', start_date='2026-09-01', end_date='2027-07-31')
            term = Term.objects.create(session=session, name='first', start_date='2026-09-01', end_date='2026-12-31')
            invoice, _ = issue_invoice(school_id=self.school.pk, term_id=term.pk, actor=self.owner, due_date=timezone.localdate())
            response = self.client.post('/api/fees/subscription/', {'invoice_id': invoice.pk})
        self.assertEqual(response.status_code, 200, response.data)
        order = PaymentOrder.objects.get()
        self.assertEqual(order.amount_kobo, 250000)
        payload = {'status': 'success', 'reference': order.reference, 'amount': order.amount_kobo,
                   'currency': 'NGN', 'domain': 'test', 'customer': {'email': self.admin.email}, 'id': 1}
        settle(order.reference, payload)
        self.school.refresh_from_db()
        ends_on = self.school.subscription_ends_on
        settle(order.reference, payload)
        self.school.refresh_from_db()
        self.assertEqual(self.school.subscription_plan, 'enterprise')
        self.assertEqual(self.school.subscription_ends_on, ends_on)

    def test_subscription_endpoint_rejects_other_tenant(self):
        self.assertEqual(self.client.get('/api/fees/subscription/', HTTP_X_SCHOOL_SLUG=self.other.subdomain).status_code, 403)

    def test_owner_can_edit_enterprise_offer(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/platform/payments/',
                                    {'plan': 'enterprise', 'amount': '2500', 'months': 3, 'enabled': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(SubscriptionOffer.objects.get(plan='enterprise').months, 3)
