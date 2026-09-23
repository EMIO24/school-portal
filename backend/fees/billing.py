"""Shared subscription quoting; issued invoices will persist these inputs separately."""
from decimal import Decimal

from enrollment.models import StudentProfile


def active_students(school):
    # Enrollment status, not login activation, determines billable enrollment.
    return StudentProfile.objects.filter(school=school, status='active')


def subscription_quote(student_count, standard_rate):
    if type(student_count) is not int or student_count < 0:
        raise ValueError('Active student count must be a non-negative integer.')
    rate = Decimal(str(standard_rate))
    if not rate.is_finite() or rate < 0 or rate != rate.quantize(Decimal('0.01')):
        raise ValueError('Rate must be a non-negative amount with at most two decimal places.')
    discount_percent = 10 if student_count >= 100 else 0
    subtotal = (rate * student_count).quantize(Decimal('0.01'))
    total = (subtotal * Decimal(100 - discount_percent) / 100).quantize(Decimal('0.01'))
    discount = subtotal - total
    return {
        'student_count': student_count,
        'standard_rate': rate,
        'discount_percent': discount_percent,
        'discount_applied': bool(discount_percent),
        'discount_amount': discount,
        'effective_rate': rate * (Decimal(100 - discount_percent) / 100),
        'subtotal': subtotal,
        'total_amount': total,
    }
