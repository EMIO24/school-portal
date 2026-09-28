"""PostgreSQL-authoritative, school-scoped student fee ledger.

Entry signs: charges/debit adjustments/opening debt positive; payments,
discounts, scholarships and credit adjustments negative. Amounts are NGN
Decimal with two places. Existing pre-cutover payments remain legacy receipts;
their original obligations cannot be reconstructed from today's schedules.
"""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from enrollment.models import StudentProfile
from tenants.models import PlatformEvent, School
from .models import (FeePayment, FeeSchedule, StudentFinanceAccount,
                     StudentLedgerEntry, StudentPaymentAllocation)

ZERO = Decimal('0.00')
MAX_MONEY = Decimal('999999999999.99')
KEY_PATTERN = re.compile(r'^[A-Za-z0-9._:-]{8,100}$')


def money(value, *, allow_zero=False, allow_negative=False):
    if isinstance(value, bool) or value is None:
        raise ValueError('Enter a valid amount in naira with at most two decimal places.')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('Enter a valid amount in naira with at most two decimal places.')
    if (not amount.is_finite() or abs(amount) > MAX_MONEY or
            amount != amount.quantize(Decimal('0.01')) or
            (amount < 0 and not allow_negative) or (amount == 0 and not allow_zero)):
        raise ValueError('Enter a valid amount in naira with at most two decimal places.')
    return amount.quantize(Decimal('0.01'))


def retry_key(value):
    if not isinstance(value, str) or not KEY_PATTERN.fullmatch(value):
        raise ValueError('A valid retry key is required for this financial change.')
    return value


def lock_school(school):
    return School.objects.select_for_update().get(pk=school.pk)


def account_for_write(school, student, *, exclude_payment=None):
    account = StudentFinanceAccount.objects.select_for_update().filter(
        school=school, student=student).first()
    if account:
        return account
    prior = FeePayment.objects.filter(school=school, student=student)
    if exclude_payment is not None:
        prior = prior.exclude(pk=exclude_payment)
    account, _ = StudentFinanceAccount.objects.get_or_create(
        school=school, student=student,
        defaults={'state': 'legacy_review' if prior.exists() else 'active'})
    return account


def entry_total(school, student, *, term=None):
    qs = StudentLedgerEntry.objects.filter(school=school, student=student)
    if term is not None:
        qs = qs.filter(term=term)
    return qs.aggregate(total=Sum('signed_amount'))['total'] or ZERO


def account_balance(school, student):
    account = StudentFinanceAccount.objects.filter(school=school, student=student).first()
    if not account:
        return {'state': 'legacy_review' if FeePayment.objects.filter(school=school, student=student).exists()
                else 'uninitialized', 'balance': None, 'outstanding': None, 'credit': None}
    if account.state != 'active':
        return {'state': 'legacy_review', 'balance': None, 'outstanding': None,
                'credit': None, 'known_since_cutover': entry_total(school, student)}
    if not StudentLedgerEntry.objects.filter(school=school, student=student).exists():
        return {'state': 'uninitialized', 'balance': None, 'outstanding': None, 'credit': None}
    balance = entry_total(school, student)
    return {'state': 'active', 'balance': balance, 'outstanding': max(balance, ZERO),
            'credit': max(-balance, ZERO)}


def balance_accounts(school, students):
    return StudentFinanceAccount.objects.filter(school=school, state='active', student__in=students).annotate(
        balance=Sum('student__ledger_entries__signed_amount',
                    filter=Q(student__ledger_entries__school=school))).exclude(balance__isnull=True)


def _audit(actor, school, student, action, entry=None):
    PlatformEvent.objects.create(actor=actor, actor_email=actor.email if actor else '',
        action='school.finance_' + action, target=str(student.pk),
        details={'school_id': school.pk, 'entry_id': entry.pk if entry else None,
                 'kind': entry.kind if entry else action,
                 'signed_amount': str(entry.signed_amount) if entry else None})


def _charge_from_schedule(school, student, schedule, actor):
    if schedule.school_id != school.pk or schedule.term.session.school_id != school.pk or \
            schedule.class_level.school_id != school.pk or schedule.fee_category.school_id != school.pk:
        raise ValueError('Fee structure must belong to this school.')
    charge, created = StudentLedgerEntry.objects.get_or_create(
        school=school, student=student, fee_schedule=schedule, kind='charge',
        defaults={'term': schedule.term, 'signed_amount': schedule.amount,
                  'description': schedule.fee_category.name,
                  'class_name_snapshot': schedule.class_level.name,
                  'due_date_snapshot': schedule.due_date,
                  'effective_date': timezone.localdate(),
                  'actor': actor, 'actor_name': actor.full_name if actor else ''})
    if created:
        _audit(actor, school, student, 'charge_created', charge)
    return charge, created


@transaction.atomic
def generate_charges(school, term, actor, *, class_arm=None):
    lock_school(school)
    if term.session.school_id != school.pk or (class_arm and class_arm.school_id != school.pk):
        raise ValueError('Select a term and class in this school.')
    students = StudentProfile.objects.filter(school=school, status='active',
        current_class__school=school).select_related('current_class__class_level')
    if class_arm:
        students = students.filter(current_class=class_arm)
    schedules = list(FeeSchedule.objects.filter(school=school, term=term)
        .select_related('term__session', 'class_level', 'fee_category'))
    by_level = {}
    for schedule in schedules:
        by_level.setdefault(schedule.class_level_id, []).append(schedule)
    opening_dates = dict(StudentLedgerEntry.objects.filter(school=school, kind='opening',
        student__in=students).values_list('student_id', 'effective_date'))
    created = existing = legacy_skipped = 0
    for student in students.iterator(chunk_size=200):
        account = account_for_write(school, student)
        for schedule in by_level.get(student.current_class.class_level_id, []):
            # Opening balances encompass old obligations; old schedules cannot be charged again.
            if account.state == 'legacy_review' or (student.pk in opening_dates and
                    schedule.term.start_date <= opening_dates[student.pk]):
                legacy_skipped += 1
                continue
            _, made = _charge_from_schedule(school, student, schedule, actor)
            created += int(made)
            existing += int(not made)
    return {'created': created, 'existing': existing, 'legacy_skipped': legacy_skipped,
            'students_considered': students.count()}


def _allocate(credit, charge, amount):
    if credit.school_id != charge.school_id or credit.student_id != charge.student_id or \
            credit.signed_amount >= 0 or charge.kind != 'charge':
        raise ValueError('Allocation must link a credit and charge in one student account.')
    applied = charge.charge_allocations.aggregate(total=Sum('amount'))['total'] or ZERO
    available = max(charge.signed_amount - applied, ZERO)
    use = min(-credit.signed_amount, available, amount)
    if use > ZERO:
        StudentPaymentAllocation.objects.create(school=credit.school, credit=credit, charge=charge, amount=use)
    return use


@transaction.atomic
def record_payment_entry(payment, *, key=''):
    school, student = payment.school, payment.student
    lock_school(school)
    if (student.school_id != school.pk or payment.fee_schedule.school_id != school.pk or
            payment.fee_schedule.term.session.school_id != school.pk or payment.amount_paid <= 0):
        raise ValueError('Payment references do not belong to one school account.')
    account = account_for_write(school, student, exclude_payment=payment.pk)
    existing = StudentLedgerEntry.objects.filter(fee_payment=payment).first()
    if existing:
        return existing
    amount = money(payment.amount_paid)
    charge = None
    if account.state == 'active':
        opening = StudentLedgerEntry.objects.filter(school=school, student=student, kind='opening').first()
        if not opening or payment.fee_schedule.term.start_date > opening.effective_date:
            charge, _ = _charge_from_schedule(school, student, payment.fee_schedule, payment.recorded_by)
    entry = StudentLedgerEntry.objects.create(school=school, student=student,
        term=payment.fee_schedule.term, fee_schedule=payment.fee_schedule, fee_payment=payment,
        kind='payment', signed_amount=-amount, description='Fee payment',
        reference=payment.receipt_number, effective_date=payment.payment_date,
        actor=payment.recorded_by,
        actor_name=payment.recorded_by.full_name if payment.recorded_by else '',
        idempotency_key=key)
    if charge:
        _allocate(entry, charge, amount)
    _audit(payment.recorded_by, school, student, 'payment_recorded', entry)
    return entry


@transaction.atomic
def post_adjustment(school, student, actor, *, kind, amount, reason, key,
                    term=None, schedule=None, reference='', effective_date=None):
    lock_school(school)
    if student.school_id != school.pk or (term and term.session.school_id != school.pk) or \
            (schedule and schedule.school_id != school.pk):
        raise ValueError('Financial references must belong to this school.')
    retry_key(key)
    if kind not in ('opening', 'discount', 'scholarship', 'adjustment'):
        raise ValueError('Choose a supported financial change.')
    if not isinstance(reason, str) or not reason.strip() or len(reason.strip()) > 500:
        raise ValueError('Record a reason of up to 500 characters.')
    if not isinstance(reference, str) or len(reference) > 100:
        raise ValueError('Use a source reference of at most 100 characters.')
    explicit_date = effective_date is not None
    if explicit_date:
        try:
            effective_date = date.fromisoformat(effective_date) if isinstance(effective_date, str) else effective_date
        except ValueError:
            raise ValueError('Use YYYY-MM-DD for the effective date.')
        if not isinstance(effective_date, date) or effective_date > timezone.localdate():
            raise ValueError('Effective date must be a valid date no later than today.')
    effective_date = effective_date or timezone.localdate()
    signed = money(amount, allow_zero=kind == 'opening', allow_negative=kind in ('opening', 'adjustment'))
    if kind in ('discount', 'scholarship'):
        signed = -signed
    existing = StudentLedgerEntry.objects.filter(school=school, idempotency_key=key).first()
    if existing:
        if (existing.student_id != student.pk or existing.kind != kind or
                existing.signed_amount != signed or existing.reason != reason.strip() or
                (explicit_date and existing.effective_date != effective_date) or existing.reference != reference or
                existing.term_id != (term.pk if term else schedule.term_id if schedule else None) or
                existing.fee_schedule_id != (schedule.pk if schedule else None)):
            raise ValueError('This retry key was used for different financial details.')
        return existing, False
    account = account_for_write(school, student)
    if kind == 'opening':
        if account.opened_at or (account.state == 'active' and StudentLedgerEntry.objects.filter(
                school=school, student=student).exists()):
            raise ValueError('An opening balance can be recorded only once before new account activity.')
        if StudentLedgerEntry.objects.filter(school=school, student=student, kind='charge').exists():
            raise ValueError('Review existing charges before recording an opening balance.')
    elif account.state != 'active':
        raise ValueError('Verify this legacy opening balance before making adjustments.')
    if kind in ('discount', 'scholarship') and not schedule:
        raise ValueError('Select the charge receiving this credit.')
    charge = None
    if schedule:
        charge = StudentLedgerEntry.objects.filter(school=school, student=student,
            fee_schedule=schedule, kind='charge').first()
        if not charge and kind != 'opening':
            raise ValueError('Generate this student charge before applying a credit or adjustment.')
    entry = StudentLedgerEntry.objects.create(school=school, student=student,
        term=term or (schedule.term if schedule else None), fee_schedule=schedule,
        kind=kind, signed_amount=signed, description={
            'opening': 'Verified opening balance', 'discount': 'Discount',
            'scholarship': 'Scholarship', 'adjustment': 'Financial adjustment'}[kind],
        reason=reason.strip(), reference=reference, effective_date=effective_date,
        actor=actor, actor_name=actor.full_name, idempotency_key=key)
    if kind == 'opening':
        account.state = 'active'
        account.opened_at = timezone.now()
        account.opened_by = actor
        account.save(update_fields=['state', 'opened_at', 'opened_by'])
    elif charge and signed < 0:
        _allocate(entry, charge, -signed)
    _audit(actor, school, student, kind + '_recorded', entry)
    return entry, True
