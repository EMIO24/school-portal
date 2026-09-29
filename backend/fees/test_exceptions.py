from unittest.mock import patch

from django.forms.models import model_to_dict
from django.test import TestCase, override_settings

from accounts.models import CustomUser
from tenants.models import PlatformEvent, PlatformSecurity
from . import tests as payment_tests
from .models import PaymentException, PaymentOrder, FeePayment
from .payments import settle


@override_settings(PAYSTACK_SECRET_KEY='sk_test_fixture', PAYSTACK_MODE='test', FRONTEND_URL='http://localhost:3001')
class PaymentExceptionTests(TestCase):
    start = payment_tests.PaystackTests.start
    data = payment_tests.PaystackTests.data
    school_url = '/api/fees/exceptions/'
    owner_url = '/api/platform/payment-exceptions/'

    def setUp(self):
        payment_tests.PaystackTests.setUp(self)
        self.network = patch('requests.sessions.Session.request', side_effect=AssertionError('No provider calls allowed'))
        self.network_mock = self.network.start()
        self.addCleanup(self.network.stop)
        self.start()
        self.order = PaymentOrder.objects.get()
        settle(self.order.reference, self.data(self.order))
        self.order.refresh_from_db()
        self.client.force_authenticate(self.admin)

    def create(self, kind='refund', reference=None, **extra):
        return self.client.post(self.school_url, {'reference': reference or self.order.reference,
            'kind': kind, 'reason': 'Please investigate this payment.', **extra}, format='json', **self.headers)

    def change(self, case, state, note='Investigated by owner.', **extra):
        case.refresh_from_db()
        return self.client.patch(f'{self.owner_url}{case.pk}/', {'expected_status': case.status,
            'status': state, 'admin_notes': note, **extra}, format='json')

    def case(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        self.client.force_authenticate(self.owner)
        return PaymentException.objects.get(pk=response.data['id'])

    def test_authorized_request_and_replay_are_one_case(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create().status_code, 200)
        self.assertEqual(PaymentException.objects.count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action='payment.exception').count(), 1)
        self.assertEqual(self.create(reason='A different submission.').status_code, 409)
        self.network_mock.assert_not_called()

    def test_school_and_ordinary_users_cannot_review_or_read_internal_notes(self):
        case = self.case()
        self.assertEqual(self.change(case, 'under_review', note='Private investigation').status_code, 200)
        parent = CustomUser.objects.create_user('parent@exceptions.test', role='parent', school=self.school)
        teacher = CustomUser.objects.create_user('teacher@exceptions.test', role='teacher', school=self.school)
        for user in (self.admin, self.user, parent, teacher):
            self.client.force_authenticate(user)
            for state in ('approved', 'rejected'):
                self.assertEqual(self.change(case, state).status_code, 403)
            self.assertEqual(self.client.get(f'{self.owner_url}{case.pk}/').status_code, 403)
        self.client.force_authenticate(self.admin)
        for url in (self.school_url, f'{self.school_url}{case.pk}/'):
            response = self.client.get(url, **self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('Private investigation', response.content.decode())
            self.assertNotIn('admin_notes', response.content.decode())
        self.assertEqual(self.client.patch(f'{self.school_url}{case.pk}/', {}, format='json', **self.headers).status_code, 405)

    def test_platform_viewer_and_anonymous_denied(self):
        case = self.case()
        PlatformSecurity.objects.create(user=self.owner, access_level='viewer')
        self.assertEqual(self.change(case, 'under_review').status_code, 403)
        self.assertEqual(self.client.get(self.owner_url).status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(self.school_url, **self.headers).status_code, (401, 403))

    def test_cross_tenant_cases_and_payment_references_are_inaccessible(self):
        case = self.case()
        foreign_admin = CustomUser.objects.create_user('admin@other.test', role='school_admin', school=self.other)
        self.client.force_authenticate(foreign_admin)
        headers = {'HTTP_X_SCHOOL_SLUG': self.other.slug}
        self.assertEqual(self.client.get(self.school_url, **headers).data['results'], [])
        self.assertEqual(self.client.get(f'{self.school_url}{case.pk}/', **headers).status_code, 404)
        response = self.client.post(self.school_url, {'reference': self.order.reference, 'kind': 'manual', 'reason': 'Foreign access'}, format='json', **headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(f'{self.school_url}{case.pk}/', **self.headers).status_code, 403)

    def test_refund_lifecycle_preserves_order_receipts_and_subscription(self):
        before_order = model_to_dict(self.order)
        before_payments = list(FeePayment.objects.values())
        self.school.refresh_from_db()
        before_school = model_to_dict(self.school)
        case = self.case()
        for state in ('under_review', 'approved', 'provider_pending', 'provider_failed', 'provider_pending'):
            self.assertEqual(self.change(case, state).status_code, 200)
        response = self.change(case, 'resolved', provider_ref='REFUND-manual-confirmation')
        self.assertEqual(response.status_code, 200, response.data)
        count = PlatformEvent.objects.filter(action='payment.exception').count()
        self.assertEqual(self.change(case, 'resolved', provider_ref='REFUND-manual-confirmation').status_code, 200)
        self.assertEqual(PlatformEvent.objects.filter(action='payment.exception').count(), count)
        self.order.refresh_from_db(); self.school.refresh_from_db(); case.refresh_from_db()
        self.assertEqual(model_to_dict(self.order), before_order)
        self.assertEqual(list(FeePayment.objects.values()), before_payments)
        self.assertEqual(model_to_dict(self.school), before_school)
        self.assertIsNotNone(case.resolved_at)
        self.assertEqual(case.reviewed_by, self.owner)
        self.network_mock.assert_not_called()

    def test_rejection_and_invalid_transitions(self):
        case = self.case()
        self.assertEqual(self.change(case, 'approved').status_code, 400)
        self.assertEqual(self.change(case, 'under_review').status_code, 200)
        self.assertEqual(self.change(case, 'resolved').status_code, 400)
        self.assertEqual(self.change(case, 'rejected').status_code, 200)
        self.assertEqual(self.change(case, 'approved').status_code, 400)

    def test_resolution_requires_confirmation_reference(self):
        case = self.case()
        for state in ('under_review', 'approved', 'provider_pending'):
            self.assertEqual(self.change(case, state).status_code, 200)
        self.assertEqual(self.change(case, 'resolved').status_code, 400)
        self.assertEqual(self.change(case, 'provider_failed', provider_ref='premature').status_code, 400)

    def test_stale_decision_is_rejected_and_history_is_retained(self):
        case = self.case()
        self.change(case, 'under_review', note='First note')
        self.change(case, 'under_review', note='Second note')
        response = self.client.patch(f'{self.owner_url}{case.pk}/', {'expected_status': 'requested',
            'status': 'approved', 'admin_notes': 'Stale decision'}, format='json')
        self.assertEqual(response.status_code, 409)
        response = self.client.get(f'{self.owner_url}{case.pk}/')
        self.assertEqual([r['details']['admin_notes'] for r in response.data['history']], ['', 'First note', 'Second note'])

    def test_discrepancy_duplicate_and_incorrect_reports_do_not_classify_or_settle(self):
        for kind in ('duplicate', 'incorrect', 'provider', 'manual'):
            self.client.force_authenticate(self.admin)
            self.assertEqual(self.create(kind=kind).status_code, 201)
            case = PaymentException.objects.get(kind=kind)
            self.client.force_authenticate(self.owner)
            self.assertEqual(self.change(case, 'under_review').status_code, 200)
            self.assertEqual(self.change(case, 'approved').status_code, 400)
            self.assertEqual(self.change(case, 'resolved').status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'success')
        self.assertEqual(FeePayment.objects.count(), 1)

    def test_unverified_payments_use_review_cases_not_refund_approval(self):
        for state in ('pending', 'failed', 'review'):
            PaymentOrder.objects.filter(pk=self.order.pk).update(status=state)
            self.assertEqual(self.create().status_code, 400)
        self.assertEqual(self.create(kind='provider').status_code, 201)
        self.assertEqual(PaymentException.objects.count(), 1)

    def test_filters_and_unsupported_amount_or_payment_edits(self):
        self.assertEqual(self.create(amount='100.00').status_code, 400)
        self.create()
        response = self.client.get(self.school_url, {'kind': 'refund', 'status': 'requested', 'reference': self.order.reference}, **self.headers)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(self.client.get(self.school_url, {'kind': 'duplicate'}, **self.headers).data['results'], [])
        self.assertEqual(self.client.get(self.school_url, {'status': 'invented'}, **self.headers).status_code, 400)
        self.assertEqual(self.client.delete(f'{self.school_url}{PaymentException.objects.get().pk}/', **self.headers).status_code, 405)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.patch(self.owner_url, {}, format='json').status_code, 400)

    def test_subscription_refund_case_does_not_extend_or_cancel_subscription(self):
        order = PaymentOrder.objects.create(school=self.school, payer=self.admin, kind='subscription',
            reference='SUB-exception-test', mode='test', amount_kobo=80000, payer_email=self.admin.email, plan='basic', months=3)
        settle(order.reference, self.data(order))
        self.school.refresh_from_db()
        expiry = self.school.subscription_ends_on
        response = self.create(reference=order.reference)
        self.assertEqual(response.status_code, 201)
        self.client.force_authenticate(self.owner)
        case = PaymentException.objects.get(pk=response.data['id'])
        for state in ('under_review', 'approved', 'provider_pending'):
            self.assertEqual(self.change(case, state).status_code, 200)
        self.assertEqual(self.change(case, 'resolved', provider_ref='SUB-refund-confirmation').status_code, 200)
        self.school.refresh_from_db(); order.refresh_from_db()
        self.assertEqual(self.school.subscription_ends_on, expiry)
        self.assertEqual(self.school.subscription_plan, 'basic')
        self.assertEqual(order.status, 'success')
