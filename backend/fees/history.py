def fee_schedule_has_history(schedule_id, school_id):
    from .models import FeePayment, StudentLedgerEntry, PaymentOrder

    if FeePayment.objects.filter(school_id=school_id, fee_schedule_id=schedule_id).exists():
        return True
    if StudentLedgerEntry.objects.filter(school_id=school_id, fee_schedule_id=schedule_id).exists():
        return True
    for allocations in PaymentOrder.objects.filter(
            school_id=school_id, kind='fees').values_list('allocations', flat=True).iterator():
        if any(item.get('schedule_id') == schedule_id for item in (allocations or []) if isinstance(item, dict)):
            return True
    return False
