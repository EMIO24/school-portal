"""Invoice checkout reuses provider initialization and the existing settlement entry point."""
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from requests.exceptions import RequestException
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from tenants.models import School
from .invoice_views import StrictInput
from .invoices import invoice_event, record_invoice_payment
from .models import PaymentOrder, TermInvoice
from .services.paystack import PaystackService


class InvoiceCheckoutInput(StrictInput):
    invoice_id = serializers.IntegerField(min_value=1)


def amount_in_kobo(amount):
    value = Decimal(amount) * 100
    if not value.is_finite() or value <= 0 or value != value.to_integral_value():
        raise ValidationError('This invoice does not have a payable amount.')
    return int(value)


@transaction.atomic
def initialize_invoice_payment(request):
    from .payments import checkout, settle
    form = InvoiceCheckoutInput(data=request.data)
    form.is_valid(raise_exception=True)
    school = School.objects.select_for_update().get(pk=request.tenant.pk)
    invoice = get_object_or_404(TermInvoice.objects.select_for_update(), pk=form.validated_data['invoice_id'], school=school)
    if invoice.status != 'issued':
        raise ValidationError('Only unpaid invoices can be paid.')
    if not invoice.subscription_months:
        raise ValidationError('The platform owner must confirm this invoice’s billing duration before payment.')
    amount = amount_in_kobo(invoice.final_amount)
    if school.approval_status != 'approved' or not school.is_active:
        raise ValidationError('Your school must be active and approved before subscribing.')
    if school.subscription_ends_on and school.subscription_ends_on >= timezone.localdate() and school.subscription_plan not in ('free', invoice.plan):
        raise ValidationError('Contact the platform owner to change plans during a paid period.')
    # Legacy outstanding attempts must be resolved too, preventing parallel billing paths.
    previous = PaymentOrder.objects.filter(school=school, kind='subscription',
        status__in=['initializing', 'pending', 'review']).order_by('id').first()
    if previous:
        if previous.mode != settings.PAYSTACK_MODE:
            return Response({'error': 'A payment from another provider mode needs owner review.', 'reference': previous.reference}, status=409)
        if previous.status == 'pending':
            try:
                previous = settle(previous.reference, PaystackService().verify(previous.reference))
            except (ValueError, RequestException):
                return Response({'error': 'Verification is unavailable. Check the existing payment before trying again.', 'reference': previous.reference}, status=409)
        invoice.refresh_from_db()
        if invoice.status == 'paid':
            return Response({'error': 'This invoice is already paid.', 'reference': previous.reference}, status=409)
        if previous.status != 'failed':
            if previous.invoice_id == invoice.pk and previous.status == 'pending' and previous.authorization_url:
                return Response({'authorization_url': previous.authorization_url, 'reference': previous.reference})
            return Response({'error': 'An unfinished payment needs verification before another checkout.', 'reference': previous.reference}, status=409)
    return checkout(request, invoice=invoice, kind='subscription', plan=invoice.plan,
                    months=invoice.subscription_months, amount_kobo=amount, currency=invoice.currency)


def settle_invoice_order(order, school, data):
    """Called inside settle's school/order transaction after trusted provider validation."""
    from .payments import add_months, event
    invoice = TermInvoice.objects.select_for_update().get(pk=order.invoice_id)
    valid = (order.kind == 'subscription' and invoice.school_id == order.school_id
             and order.reference.startswith(f'SCH-I{invoice.pk}-')
             and invoice.status == 'issued' and order.plan == invoice.plan
             and order.months == invoice.subscription_months and order.amount_kobo == invoice.final_amount * 100
             and order.currency == invoice.currency and order.created_at >= invoice.snapshot_at)
    today = timezone.localdate()
    if school.subscription_ends_on and school.subscription_ends_on >= today and school.subscription_plan not in ('free', invoice.plan):
        valid = False
    if not valid:
        order.status, order.note = 'review', 'Invoice or subscription details require owner review. No credit was applied.'
        order.save(update_fields=['status', 'note'])
        event(None, 'invoice.payment_mismatch', order.reference, {'invoice_id': invoice.pk, 'school_id': order.school_id})
        return order
    order.status, order.paid_at, order.provider_id, order.note = 'success', timezone.now(), str(data.get('id', '')), ''
    order.save(update_fields=['status', 'paid_at', 'provider_id', 'note'])
    record_invoice_payment(invoice.pk, payment_id=order.pk)
    school.subscription_plan = invoice.plan
    school.subscription_ends_on = add_months(max(today, school.subscription_ends_on or today), invoice.subscription_months)
    school.save(update_fields=['subscription_plan', 'subscription_ends_on'])
    event(order.payer, 'payment.verified', order.reference, {'school_id': school.pk, 'invoice_id': invoice.pk, 'amount_kobo': order.amount_kobo})
    return order


@transaction.atomic
def assign_legacy_duration(invoice_id, *, months, actor):
    school_id = get_object_or_404(TermInvoice, pk=invoice_id).school_id
    School.objects.select_for_update().get(pk=school_id)
    invoice = get_object_or_404(TermInvoice.objects.select_for_update(), pk=invoice_id)
    if invoice.subscription_months is not None or invoice.status != 'issued' or invoice.payment_attempts.exists():
        raise ValidationError('Duration can only be assigned once to an unpaid legacy invoice with no payment attempts.')
    if type(months) is not int or not 1 <= months <= 12:
        raise ValidationError('Choose a billing duration from 1 to 12 months.')
    from django.db.models import QuerySet
    QuerySet.update(TermInvoice.objects.filter(pk=invoice.pk), subscription_months=months)
    invoice.refresh_from_db()
    invoice_event(invoice, actor, 'duration_assigned', months=months)
    return invoice
