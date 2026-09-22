"""Durable Paystack checkout and settlement; never trust a browser payment result."""
import calendar
import hashlib
import hmac
import json
import logging
import uuid
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode, urlparse
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from requests.exceptions import RequestException
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.permissions import IsAuthenticatedTenantUser, IsSchoolAdmin, IsSuperAdmin
from enrollment.models import StudentProfile
from tenants.models import School, PlatformEvent
from tenants.plans import PLAN_FEATURES, FEATURES
from .models import PaymentOrder, SchoolPaymentAccount, SubscriptionOffer, FeeSchedule, FeePayment
from .access import payment_student
from .services.paystack import PaystackService


logger = logging.getLogger(__name__)


def subscription_student_count(school):
    return StudentProfile.objects.filter(school=school, status='active').count()


def subscription_offer_total(school, offer):
    student_count = subscription_student_count(school)
    amount = Decimal(student_count) * Decimal(str(offer.amount))
    if student_count >= 100:
        amount *= Decimal('0.90')
    return amount.quantize(Decimal('0.01'))


def subscription_offer_amount(school, offer):
    return subscription_offer_total(school, offer)


def event(user, action, target, details):
    PlatformEvent.objects.create(actor=user, actor_email=user.email if user else '', action=action, target=str(target), details=details)


def checkout(request, **values):
    try:
        service = PaystackService()
        origin = settings.FRONTEND_URL.rstrip('/')
        parsed = urlparse(origin)
        if parsed.scheme not in ('https', 'http') or not parsed.netloc or (service.mode == 'live' and parsed.scheme != 'https'):
            raise ValueError('Configure FRONTEND_URL before accepting payments.')
    except ValueError as exc:
        logger.error("payment_checkout_configuration_failed kind=%s error_type=%s", values.get('kind', 'unknown'), type(exc).__name__)
        return Response({'error': str(exc)}, status=503)
    order = PaymentOrder.objects.create(school=request.tenant, payer=request.user,
        payer_email=request.user.email, mode=service.mode, reference='SCH-' + uuid.uuid4().hex, **values)
    callback = origin + '/payments/return?' + urlencode({'school': request.tenant.subdomain})
    try:
        url, _ = service.initialize(order.payer_email, order.amount_kobo, order.reference, callback, subaccount=order.subaccount_code or None)
    except (RequestException, ValueError) as exc:
        logger.warning("payment_initialization_failed order_id=%s reference=%s kind=%s error_type=%s", order.pk, order.reference, order.kind, type(exc).__name__)
        # A timeout can occur AFTER Paystack creates the transaction. Keep its reference.
        return Response({'error': 'Unable to start checkout. Contact your school with this reference before retrying.', 'reference': order.reference}, status=502)
    PaymentOrder.objects.filter(pk=order.pk, status='initializing').update(status='pending', authorization_url=url)
    return Response({'authorization_url': url, 'reference': order.reference})


def add_months(day, months):
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


@transaction.atomic
def settle(reference, data):
    order = PaymentOrder.objects.select_for_update().get(reference=reference)
    if order.status == 'success':
        logger.info("payment_settlement_idempotent order_id=%s reference=%s", order.pk, order.reference)
        return order
    if not isinstance(data, dict):
        return order
    if data.get('status') in ('failed', 'abandoned') and data.get('reference') == order.reference and data.get('domain') == order.mode == settings.PAYSTACK_MODE:
        order.status = 'failed'
        order.save(update_fields=['status'])
        logger.info("payment_status_changed order_id=%s reference=%s status=failed provider_status=%s", order.pk, order.reference, data.get('status'))
        return order
    if data.get('status') != 'success':
        return order
    customer = data.get('customer') or {}
    valid = (data.get('reference') == order.reference and type(data.get('amount')) is int
        and data['amount'] == order.amount_kobo and data.get('currency') == order.currency
        and data.get('domain') == order.mode == settings.PAYSTACK_MODE
        and isinstance(customer, dict) and str(customer.get('email', '')).lower() == order.payer_email.lower())
    if not valid:
        order.status, order.note = 'review', 'Payment details did not match the checkout. Contact the platform owner.'
        order.save(update_fields=['status', 'note'])
        event(None, 'payment.mismatch', order.reference, {'school_id': order.school_id})
        logger.warning("payment_review_required order_id=%s reference=%s reason=validation_mismatch", order.pk, order.reference)
        return order
    school = School.objects.select_for_update().get(pk=order.school_id)
    if order.kind == 'fees':
        for allocation in order.allocations:
            schedule = FeeSchedule.objects.filter(pk=allocation['schedule_id'], school=school).first()
            paid = FeePayment.objects.filter(student=order.student, fee_schedule=schedule).aggregate(total=Sum('amount_paid'))['total'] or Decimal(0)
            if schedule is None or int(max(Decimal(0), schedule.amount - paid) * 100) < allocation['amount_kobo']:
                order.status, order.note = 'review', 'Fee balance changed; contact the owner to reconcile or refund this payment.'
                order.save(update_fields=['status', 'note'])
                logger.warning("payment_review_required order_id=%s reference=%s reason=balance_changed", order.pk, order.reference)
                return order
        for allocation in order.allocations:
            FeePayment.objects.create(school=school, student=order.student,
                fee_schedule_id=allocation['schedule_id'], amount_paid=Decimal(allocation['amount_kobo']) / 100,
                payment_date=timezone.localdate(), method='paystack', paystack_reference=reference,
                paystack_status='success', recorded_by=order.payer)
    else:
        today = timezone.localdate()
        if school.subscription_ends_on and school.subscription_ends_on >= today and school.subscription_plan not in ('free', order.plan):
            order.status, order.note = 'review', 'Plan changed while payment was pending. Owner review required.'
            order.save(update_fields=['status', 'note'])
            logger.warning("payment_review_required order_id=%s reference=%s reason=plan_changed", order.pk, order.reference)
            return order
        start = max(today, school.subscription_ends_on or today)
        school.subscription_plan = order.plan
        school.subscription_ends_on = add_months(start, order.months)
        school.save(update_fields=['subscription_plan', 'subscription_ends_on'])
        # Paying never overrides manual approval or suspension.
    order.status, order.paid_at, order.provider_id, order.note = 'success', timezone.now(), str(data.get('id', '')), ''
    order.save(update_fields=['status', 'paid_at', 'provider_id', 'note'])
    event(order.payer, 'payment.verified', reference, {'school_id': school.pk, 'kind': order.kind, 'amount_kobo': order.amount_kobo})
    logger.info("payment_settled order_id=%s reference=%s kind=%s school_id=%s", order.pk, order.reference, order.kind, school.pk)
    return order


def result(order):
    return {'reference': order.reference, 'status': order.status, 'kind': order.kind,
        'amount': str(Decimal(order.amount_kobo) / 100), 'note': order.note,
        'receipts': list(FeePayment.objects.filter(paystack_reference=order.reference, school=order.school).values('id', 'receipt_number'))}


class PaystackInitiateView(APIView):
    permission_classes = [IsAuthenticatedTenantUser]
    @transaction.atomic
    def post(self, request):
        School.objects.select_for_update().get(pk=request.tenant.pk)
        student = payment_student(request, request.data.get('student_id'))
        ids = request.data.get('fee_schedule_ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(type(i) is not int for i in ids) or len(set(ids)) != len(ids):
            raise ValidationError('Select valid, distinct fee schedules.')
        if not student.current_class:
            raise ValidationError('Assign the student to a class first.')
        schedules = list(FeeSchedule.objects.filter(school=request.tenant, pk__in=ids, class_level=student.current_class.class_level))
        if len(schedules) != len(ids):
            raise ValidationError('One or more fees do not belong to this student.')
        account = SchoolPaymentAccount.objects.filter(school=request.tenant, mode=settings.PAYSTACK_MODE).first()
        if not account:
            return Response({'error': 'Your school has not connected its Paystack settlement account. Contact your school administrator.'}, status=409)
        pending = PaymentOrder.objects.filter(
            student=student,
            kind='fees',
            mode=settings.PAYSTACK_MODE,
            status__in=['initializing', 'pending', 'review']
        )

        for previous in pending:
            previous_schedule_ids = {
                allocation['schedule_id']
                for allocation in previous.allocations
            }

            if not (set(ids) & previous_schedule_ids):
                continue

            # A Paystack checkout may have failed while the local order
            # remained pending because no verify request/webhook followed.
            if previous.status == 'pending':
                try:
                    service = PaystackService()
                    data = service.verify(previous.reference)
                    previous = settle(previous.reference, data)
                except (RequestException, ValueError):
                    # If Paystack cannot be reached or verification is invalid,
                    # fail closed: do not risk creating a duplicate checkout.
                    return Response({
                        'error': 'The previous payment could not be verified. Check it before paying again.',
                        'reference': previous.reference
                    }, status=409)

                # Failed/abandoned transactions are now reconciled and should
                # no longer prevent the user from starting another checkout.
                if previous.status == 'failed':
                    continue

                # If verification discovered a successful payment, don't create
                # another checkout. The outstanding balance will be recalculated
                # below.
                if previous.status == 'success':
                    continue

            return Response({
                'error': 'A payment for these fees is awaiting verification. Check it before paying again.',
                'reference': previous.reference
            }, status=409)
        allocations = []
        for schedule in schedules:
            paid = FeePayment.objects.filter(student=student, fee_schedule=schedule).aggregate(total=Sum('amount_paid'))['total'] or Decimal(0)
            outstanding = int(max(Decimal(0), schedule.amount - paid) * 100)
            if outstanding:
                allocations.append({'schedule_id': schedule.pk, 'amount_kobo': outstanding})
        if not allocations:
            raise ValidationError('The selected fees are already paid.')
        return checkout(request, kind='fees', student=student, subaccount_code=account.subaccount_code,
            amount_kobo=sum(a['amount_kobo'] for a in allocations), allocations=allocations)


class PaystackVerifyView(APIView):
    permission_classes = [IsAuthenticatedTenantUser]
    def get(self, request):
        order = get_object_or_404(PaymentOrder, reference=request.query_params.get('reference', ''), school=request.tenant)
        if request.user.school_id != order.school_id or (order.payer_id != request.user.pk and request.user.role != 'school_admin'):
            raise PermissionDenied()
        if order.status != 'success':
            try:
                order = settle(order.reference, PaystackService().verify(order.reference))
            except (RequestException, ValueError) as exc:
                logger.warning("payment_verification_failed order_id=%s reference=%s error_type=%s", order.pk, order.reference, type(exc).__name__)
                return Response({'error': 'Verification unavailable. Your payment reference is saved; try verification again.'}, status=502)
        return Response(result(order))


class PaystackWebhook(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    def post(self, request):
        try:
            service = PaystackService()
        except ValueError as exc:
            logger.error("paystack_webhook_configuration_failed error_type=%s", type(exc).__name__)
            return Response(status=503)
        signature = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), request.body, hashlib.sha512).hexdigest()
        if not hmac.compare_digest(signature.encode(), request.headers.get('x-paystack-signature', '').encode()):
            logger.warning("paystack_webhook_rejected reason=invalid_signature")
            return Response(status=403)
        try:
            payload = json.loads(request.body)
            reference = payload['data']['reference']
        except (ValueError, KeyError, TypeError):
            logger.warning("paystack_webhook_rejected reason=invalid_payload")
            return Response(status=400)
        if payload.get('event') != 'charge.success':
            logger.info("paystack_webhook_ignored reason=unsupported_event")
            return Response(status=200)
        if not PaymentOrder.objects.filter(reference=reference).exists():
            logger.warning("paystack_webhook_ignored reason=unknown_reference reference=%s", reference)
            return Response(status=200)
        try:
            settle(reference, service.verify(reference))
        except (RequestException, ValueError) as exc:
            logger.error("paystack_webhook_processing_failed reference=%s error_type=%s", reference, type(exc).__name__)
            return Response(status=502)
        return Response(status=200)


class SchoolSubscription(APIView):
    permission_classes = [IsSchoolAdmin]
    def get(self, request):
        offers = []
        school_student_count = StudentProfile.objects.filter(school=request.tenant, status='active').count()
        for offer in SubscriptionOffer.objects.filter(enabled=True):
            base_amount = Decimal(str(offer.amount))
            total_amount = Decimal(school_student_count) * base_amount
            if school_student_count >= 100:
                total_amount *= Decimal('0.90')
            offers.append({
                'plan': offer.plan,
                'amount': float(offer.amount),
                'months': offer.months,
                'base_amount': float(offer.amount),
                'total_amount': float(total_amount.quantize(Decimal('0.01'))),
                'student_count': school_student_count,
                'discount_percent': 10 if school_student_count >= 100 else 0,
                'discount_applied': school_student_count >= 100,
                'billing_note': 'per student per term',
            })
        school_summary = f"School size: {school_student_count} active students."
        if school_student_count >= 100:
            school_summary += ' 10% discount is active.'
        else:
            school_summary += ' 100+ active students unlocks 10% off.'
        return Response({'plan': request.tenant.subscription_plan, 'ends_on': request.tenant.subscription_ends_on,
            'features': PLAN_FEATURES,
            'feature_labels': FEATURES,
            'school_size_summary': school_summary,
            'school_student_count': school_student_count,
            'offers': offers,
            'orders': [result(o) for o in PaymentOrder.objects.filter(school=request.tenant, kind='subscription').order_by('-id')[:30]]})
    @transaction.atomic
    def post(self, request):
        school = School.objects.select_for_update().get(pk=request.tenant.pk)
        previous = PaymentOrder.objects.filter(
            school=school,
            kind='subscription',
            mode=settings.PAYSTACK_MODE,
            status__in=['initializing', 'pending', 'review']
        ).first()

        if previous:
            if previous.status == 'pending':
                try:
                    paystack_data = PaystackService().verify(previous.reference)
                    previous = settle(previous.reference, paystack_data)
                except (ValueError, RequestException):
                    return Response({
                        'error': (
                            'The previous subscription payment could not be verified. '
                            'Check it before paying again.'
                        ),
                        'reference': previous.reference,
                    }, status=409)

                if previous.status == 'failed':
                    previous = None

            if previous:
                return Response({
                    'error': (
                        'A subscription payment is awaiting verification. '
                        'Check its status before paying again.'
                    ),
                    'reference': previous.reference,
                }, status=409)
        if school.approval_status != 'approved':
            raise ValidationError('Your school must be approved before subscribing.')
        offer = get_object_or_404(SubscriptionOffer, plan=request.data.get('plan'), enabled=True)
        if school.subscription_ends_on and school.subscription_ends_on >= timezone.localdate() and school.subscription_plan not in ('free', offer.plan):
            raise ValidationError('Contact the platform owner to change plans during a paid period.')
        final_amount = subscription_offer_total(school, offer)
        return checkout(request, kind='subscription', plan=offer.plan, months=offer.months, amount_kobo=int(final_amount * 100))


class PlatformPayments(APIView):
    permission_classes = [IsSuperAdmin]
    def get(self, request):
        try:
            PaystackService()
            configured = True
        except ValueError:
            configured = False
        orders = PaymentOrder.objects.order_by('-id')
        status = request.query_params.get('status')
        kind = request.query_params.get('kind')
        school_id = request.query_params.get('school_id')
        if status:
            if status not in dict(PaymentOrder._meta.get_field('status').choices):
                raise ValidationError('Select a valid payment status.')
            orders = orders.filter(status=status)
        if kind:
            if kind not in dict(PaymentOrder._meta.get_field('kind').choices):
                raise ValidationError('Select a valid payment type.')
            orders = orders.filter(kind=kind)
        if school_id:
            try:
                orders = orders.filter(school_id=int(school_id))
            except (TypeError, ValueError):
                raise ValidationError('Select a valid school.')
        return Response({'mode': settings.PAYSTACK_MODE, 'configured': configured,
            'schools': list(School.objects.order_by('name').values('id', 'name')),
            'offers': list(SubscriptionOffer.objects.values('plan', 'amount', 'months', 'enabled')),
            'accounts': list(SchoolPaymentAccount.objects.filter(mode=settings.PAYSTACK_MODE).values('school_id', 'business_name', 'bank_name', 'account_last_four', 'subaccount_code')),
            'orders': [dict(result(o), school_id=o.school_id) for o in orders[:100]]})
    def post(self, request):
        if request.data.get('action') == 'retry_checkout':
            order = get_object_or_404(PaymentOrder, reference=request.data.get('reference'), mode=settings.PAYSTACK_MODE)
            if order.status not in ('initializing','pending'):
                raise ValidationError('Only unfinished checkouts can be reopened.')
            if order.authorization_url:
                return Response({'authorization_url':order.authorization_url,'reference':order.reference})
            try:
                callback = settings.FRONTEND_URL.rstrip('/') + '/payments/return?' + urlencode({'school':order.school.subdomain})
                url, _ = PaystackService().initialize(order.payer_email, order.amount_kobo, order.reference, callback, subaccount=order.subaccount_code or None)
            except (ValueError, RequestException):
                return Response({'error':'Checkout could not be reopened. Verify this reference in Paystack; no new order was created.'}, status=502)
            PaymentOrder.objects.filter(pk=order.pk, status='initializing').update(status='pending',authorization_url=url)
            event(request.user, 'payment.checkout_reopened', order.reference, {'school_id':order.school_id})
            return Response({'authorization_url':url,'reference':order.reference})
        if 'reference' in request.data:
            order = get_object_or_404(PaymentOrder, reference=request.data['reference'])
            previous_status = order.status
            try:
                order = settle(order.reference, PaystackService().verify(order.reference))
            except (ValueError, RequestException) as exc:
                logger.error("payment_reconciliation_failed order_id=%s reference=%s status=%s error_type=%s", order.pk, order.reference, order.status, type(exc).__name__)
                return Response({'error': 'Paystack verification unavailable. No credit was applied.'}, status=502)
            logger.info("payment_reconciliation_completed order_id=%s reference=%s previous_status=%s resulting_status=%s", order.pk, order.reference, previous_status, order.status)
            return Response(result(order))
        from rest_framework import serializers
        class OfferInput(serializers.Serializer):
            plan = serializers.ChoiceField(choices=['basic', 'premium'])
            amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('100'))
            months = serializers.IntegerField(min_value=1, max_value=12)
            enabled = serializers.BooleanField()
        form = OfferInput(data=request.data)
        form.is_valid(raise_exception=True)
        values = dict(form.validated_data)
        plan = values.pop('plan')
        with transaction.atomic():
            SubscriptionOffer.objects.update_or_create(plan=plan, defaults=values)
            event(request.user, 'subscription.offer_updated', plan, {**values, 'amount': str(values['amount'])})
        return self.get(request)


class PlatformPaymentAccount(APIView):
    permission_classes = [IsSuperAdmin]
    def post(self, request, pk):
        school = get_object_or_404(School, pk=pk)
        code = request.data.get('subaccount_code', '')
        if not isinstance(code, str) or not code.startswith('ACCT_') or len(code) > 100:
            raise ValidationError('Enter the school subaccount code from Paystack (ACCT_...).')
        try:
            service = PaystackService()
            data = service.subaccount(code)
        except (ValueError, RequestException):
            return Response({'error': 'Unable to verify this subaccount with Paystack.'}, status=502)
        if data.get('subaccount_code') != code or data.get('active') is not True or data.get('currency') != 'NGN' or data.get('domain') != service.mode:
            raise ValidationError('Subaccount must be active, NGN, and match the current Paystack mode.')
        from django.db import IntegrityError
        try:
            with transaction.atomic():
                SchoolPaymentAccount.objects.update_or_create(school=school, mode=service.mode, defaults={
                    'subaccount_code': code, 'business_name': data['business_name'], 'bank_name': data.get('settlement_bank', ''),
                    'account_last_four': str(data.get('account_number', ''))[-4:]})
                event(request.user, 'payment.account_connected', school.pk, {'code': code, 'mode': service.mode})
        except IntegrityError:
            raise ValidationError('This subaccount is already linked to another school.')
        return Response({'business_name': data['business_name'], 'account_last_four': str(data.get('account_number', ''))[-4:]})
