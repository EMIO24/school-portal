"""Snapshot issuance and explicit, audited lifecycle transitions; no money movement."""
from uuid import NAMESPACE_URL, uuid5

from django.db import models, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from academics.models import Term
from tenants.models import PlatformEvent, School
from .billing import active_students, subscription_quote
from .models import PaymentOrder, SubscriptionOffer, TermInvoice


def invoice_event(invoice, actor, action, **details):
    PlatformEvent.objects.create(
        actor=actor, actor_email=actor.email or '', action='invoice.' + action,
        target=f'invoice:{invoice.pk}',
        details={'school_id': invoice.school_id, 'invoice_number': invoice.invoice_number, **details},
    )


@transaction.atomic
def issue_invoice(*, school_id, term_id, due_date, actor, grace_period_days=0):
    # Serializes generation per school on PostgreSQL. The unique constraint is a
    # second barrier against duplicate generation from any other code path.
    school = get_object_or_404(School.objects.select_for_update(), pk=school_id)
    term = get_object_or_404(Term.objects.select_related('session'), pk=term_id, session__school=school)
    existing = TermInvoice.objects.filter(school=school, term=term, billing_context='subscription').first()
    if existing:
        return existing, False  # Includes paid/void records; never rebill silently.
    today = timezone.localdate()
    if due_date < today or not 0 <= grace_period_days <= 365:
        raise ValidationError('Due date must not precede issue date; grace period must be 0–365 days.')
    offer = SubscriptionOffer.objects.filter(plan=school.subscription_plan, enabled=True).first()
    if offer is None:
        raise ValidationError('The school needs an enabled paid-plan offer before invoicing.')
    quote = subscription_quote(active_students(school).count(), offer.amount)
    invoice = TermInvoice.objects.create(
        school=school, academic_session=term.session, term=term,
        school_name=school.name, session_name=term.session.name, term_name=term.get_name_display(),
        plan=offer.plan, active_student_count=quote['student_count'],
        standard_rate=quote['standard_rate'], discount_applied=quote['discount_applied'],
        discount_percentage=quote['discount_percent'], discount_amount=quote['discount_amount'],
        effective_rate=quote['effective_rate'], subtotal=quote['subtotal'], final_amount=quote['total_amount'],
        invoice_number='PAI-' + uuid5(NAMESPACE_URL, f'paideia:subscription:{school.pk}:{term.pk}').hex.upper(),
        issue_date=today, due_date=due_date, grace_period_days=grace_period_days, issued_by=actor,
    )
    invoice_event(invoice, actor, 'issued', amount=str(invoice.final_amount))
    return invoice, True


def _transition(invoice, **fields):
    # Deliberate bypass of the public immutable manager, limited to lifecycle data.
    if set(fields) - {'status', 'paid_at', 'payment_id', 'voided_at', 'void_reason'}:
        raise ValueError('Only lifecycle fields may be transitioned.')
    models.QuerySet.update(TermInvoice.objects.filter(pk=invoice.pk), **fields)
    invoice.refresh_from_db()
    return invoice


@transaction.atomic
def void_invoice(invoice_id, *, actor, reason):
    invoice = get_object_or_404(TermInvoice.objects.select_for_update(), pk=invoice_id)
    if invoice.status == 'void':
        return invoice
    if invoice.status != 'issued':
        raise ValidationError('Only unpaid invoices can be voided; paid invoices require a separate refund workflow.')
    reason = reason.strip()
    if not reason or len(reason) > 500:
        raise ValidationError('Provide a reason of 1–500 characters.')
    _transition(invoice, status='void', voided_at=timezone.now(), void_reason=reason)
    invoice_event(invoice, actor, 'voided', reason=reason)
    return invoice


@transaction.atomic
def record_invoice_payment(invoice_id, *, payment_id):
    """Future reconciliation hook: accepts only an exact, verified subscription payment.

    Not called by current checkout and not exposed as an arbitrary HTTP status edit.
    """
    payment = get_object_or_404(PaymentOrder.objects.select_for_update(), pk=payment_id)
    invoice = get_object_or_404(TermInvoice.objects.select_for_update(), pk=invoice_id)
    if invoice.status == 'paid' and invoice.payment_id == payment.pk:
        return invoice
    if invoice.status != 'issued':
        raise ValidationError('Only unpaid invoices can receive a payment.')
    if (payment.status != 'success' or payment.kind != 'subscription'
            or payment.school_id != invoice.school_id or payment.plan != invoice.plan
            or payment.currency != invoice.currency or payment.amount_kobo != invoice.final_amount * 100
            or not payment.paid_at or payment.created_at < invoice.snapshot_at
            or payment.paid_at < invoice.snapshot_at):
        raise ValidationError('Payment does not match this invoice or has not been verified.')
    if TermInvoice.objects.filter(payment=payment).exists():
        raise ValidationError('Payment is already assigned to an invoice.')
    _transition(invoice, status='paid', paid_at=payment.paid_at, payment_id=payment.pk)
    invoice_event(invoice, payment.payer, 'paid', payment_id=payment.pk)
    return invoice
