from django.conf import settings
from django.db import models

from .invoice_models import TermInvoice  # Register the invoice model with this app.


class FeeCategory(models.Model):
    school         = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='fee_categories')
    name           = models.CharField(max_length=120)
    description    = models.TextField(blank=True)
    is_compulsory  = models.BooleanField(default=True)

    class Meta:
        unique_together = [('school', 'name')]
        ordering        = ['name']

    def __str__(self):
        return f"{self.name} â€” {self.school.name}"


class FeeSchedule(models.Model):
    school        = models.ForeignKey('tenants.School',           on_delete=models.CASCADE, related_name='fee_schedules')
    term          = models.ForeignKey('academics.Term',           on_delete=models.CASCADE, related_name='fee_schedules')
    class_level   = models.ForeignKey('enrollment.ClassLevel',    on_delete=models.CASCADE, related_name='fee_schedules')
    fee_category  = models.ForeignKey(FeeCategory,                on_delete=models.CASCADE, related_name='schedules')
    amount        = models.DecimalField(max_digits=10, decimal_places=2)
    due_date      = models.DateField(null=True, blank=True)

    class Meta:
        unique_together = [('term', 'class_level', 'fee_category')]
        ordering        = ['class_level__order_index', 'fee_category__name']

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values(
                'school_id', 'term_id', 'class_level_id', 'fee_category_id', 'amount', 'due_date'
            ).first()
            if previous:
                amount_value = self._meta.get_field('amount').to_python(self.amount)
                due_value = self._meta.get_field('due_date').to_python(self.due_date)
                changed = any([
                    previous['school_id'] != self.school_id,
                    previous['term_id'] != self.term_id,
                    previous['class_level_id'] != self.class_level_id,
                    previous['fee_category_id'] != self.fee_category_id,
                    previous['amount'] != amount_value,
                    previous['due_date'] != due_value,
                ])
                if changed:
                    from django.core.exceptions import ValidationError
                    from .history import fee_schedule_has_history
                    if fee_schedule_has_history(self.pk, previous['school_id']):
                        raise ValidationError(
                            'This fee schedule has financial history and cannot be rewritten.'
                        )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.fee_category.name} / {self.class_level.name} â€” â‚¦{self.amount}"


class FeePayment(models.Model):
    METHOD_CHOICES = [
        ('cash',          'Cash'),
        ('paystack',      'Paystack'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    school             = models.ForeignKey('tenants.School',                on_delete=models.CASCADE, related_name='fee_payments')
    student            = models.ForeignKey('enrollment.StudentProfile',     on_delete=models.PROTECT, related_name='fee_payments')
    fee_schedule       = models.ForeignKey(FeeSchedule,                     on_delete=models.PROTECT, related_name='payments')
    amount_paid        = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date       = models.DateField()
    method             = models.CharField(max_length=20, choices=METHOD_CHOICES)
    paystack_reference = models.CharField(max_length=100, blank=True)
    paystack_status    = models.CharField(max_length=50,  blank=True)
    receipt_number     = models.CharField(max_length=30,  unique=True, blank=True)
    receipt_snapshot   = models.JSONField(default=dict, blank=True)
    recorded_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recorded_payments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def _receipt_snapshot(self):
        school = self.school
        student = self.student
        schedule = self.fee_schedule
        theme = getattr(school, 'theme_config', {}) or {}
        actor = self.recorded_by
        return {
            'school_name': getattr(school, 'name', ''),
            'school_logo': getattr(school, 'logo', '') or '',
            'school_motto': getattr(school, 'motto', '') or '',
            'school_address': getattr(school, 'address', '') or '',
            'school_phone': getattr(school, 'phone', '') or '',
            'school_email': getattr(school, 'email', '') or '',
            'school_registration_number': getattr(school, 'registration_number', '') or '',
            'document_primary_color': theme.get('primary_color', '#173B56'),
            'document_secondary_color': theme.get('secondary_color', '#256D85'),
            'document_accent_color': theme.get('accent_color', '#D8A548'),
            'student_name': student.user.full_name or student.admission_number,
            'admission_number': student.admission_number,
            'class_name': student.current_class.full_name if student.current_class_id else '',
            'fee_category': schedule.fee_category.name,
            'term_name': schedule.term.get_name_display(),
            'session_name': schedule.term.session.name,
            'amount_paid': str(self.amount_paid),
            'payment_date': str(self.payment_date),
            'method': self.method,
            'method_label': dict(self.METHOD_CHOICES).get(self.method, self.method),
            'paystack_reference': self.paystack_reference or '',
            'issued_by': actor.full_name if actor else 'School Admin',
        }

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import uuid
            self.receipt_number = 'REC-' + uuid.uuid4().hex[:26].upper()
        if self._state.adding and not self.receipt_snapshot:
            self.receipt_snapshot = self._receipt_snapshot()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} â€” {self.student} â‚¦{self.amount_paid}"


class StudentFinanceAccount(models.Model):
    """Cutover state; balances are derived from entries, never cached here."""
    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT)
    student = models.OneToOneField('enrollment.StudentProfile', on_delete=models.PROTECT, related_name='finance_account')
    state = models.CharField(max_length=20, choices=[('active', 'Active'), ('legacy_review', 'Legacy balance needs review')])
    cutover_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    opened_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)


class StudentLedgerEntry(models.Model):
    KIND_CHOICES = [
        ('charge', 'Charge'), ('opening', 'Opening balance'), ('payment', 'Payment'),
        ('discount', 'Discount'), ('scholarship', 'Scholarship'),
        ('adjustment', 'Adjustment'), ('reversal', 'Reversal'),
    ]
    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT)
    student = models.ForeignKey('enrollment.StudentProfile', on_delete=models.PROTECT, related_name='ledger_entries')
    term = models.ForeignKey('academics.Term', on_delete=models.PROTECT, null=True, blank=True)
    fee_schedule = models.ForeignKey(FeeSchedule, on_delete=models.PROTECT, null=True, blank=True)
    fee_payment = models.OneToOneField(FeePayment, on_delete=models.PROTECT, null=True, blank=True, related_name='ledger_entry')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    signed_amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=200)
    class_name_snapshot = models.CharField(max_length=100, blank=True)
    due_date_snapshot = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    effective_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    actor_name = models.CharField(max_length=300, blank=True)
    idempotency_key = models.CharField(max_length=100, blank=True)

    class Meta:
        indexes = [models.Index(fields=['school', 'student', 'id']), models.Index(fields=['school', 'term', 'student'])]
        constraints = [
            models.UniqueConstraint(fields=['school', 'student', 'fee_schedule'],
                condition=models.Q(kind='charge', fee_schedule__isnull=False), name='unique_student_schedule_charge'),
            models.UniqueConstraint(fields=['school', 'idempotency_key'],
                condition=~models.Q(idempotency_key=''), name='unique_student_ledger_retry_key'),
            models.CheckConstraint(check=~models.Q(signed_amount=0) | models.Q(kind='opening'), name='student_ledger_nonzero'),
        ]


class StudentPaymentAllocation(models.Model):
    """Explicit amount of one credit applied to one frozen charge."""
    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT)
    credit = models.ForeignKey(StudentLedgerEntry, on_delete=models.PROTECT, related_name='credit_allocations')
    charge = models.ForeignKey(StudentLedgerEntry, on_delete=models.PROTECT, related_name='charge_allocations')
    amount = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['credit', 'charge'], name='unique_credit_charge_allocation'),
            models.CheckConstraint(check=models.Q(amount__gt=0), name='student_allocation_positive'),
        ]


class SchoolPaymentAccount(models.Model):
    school = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='payment_accounts')
    mode = models.CharField(max_length=4, choices=[('test', 'Test'), ('live', 'Live')])
    subaccount_code = models.CharField(max_length=100)
    business_name = models.CharField(max_length=255)
    bank_name = models.CharField(max_length=255, blank=True)
    account_last_four = models.CharField(max_length=4, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['school', 'mode'], name='school_payment_mode_unique'),
                       models.UniqueConstraint(fields=['subaccount_code', 'mode'], name='school_subaccount_mode_unique')]


class SubscriptionOffer(models.Model):
    plan = models.CharField(max_length=20, unique=True, choices=[('basic', 'Basic'), ('premium', 'Premium'), ('enterprise', 'Enterprise')])
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    months = models.PositiveSmallIntegerField(default=12)
    enabled = models.BooleanField(default=False)


class PaymentOrder(models.Model):
    invoice = models.ForeignKey('fees.TermInvoice', on_delete=models.PROTECT, null=True, blank=True, related_name='payment_attempts')
    received_amount_kobo = models.PositiveBigIntegerField(null=True, blank=True)
    received_currency = models.CharField(max_length=3, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT, related_name='payment_orders')
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    student = models.ForeignKey('enrollment.StudentProfile', on_delete=models.PROTECT, null=True, blank=True)
    kind = models.CharField(max_length=20, choices=[('fees', 'School fees'), ('subscription', 'Portal subscription')])
    reference = models.CharField(max_length=100, unique=True)
    request_key = models.CharField(max_length=100, blank=True)
    mode = models.CharField(max_length=4)
    amount_kobo = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default='NGN')
    payer_email = models.EmailField()
    subaccount_code = models.CharField(max_length=100, blank=True)
    allocations = models.JSONField(default=list)
    plan = models.CharField(max_length=20, blank=True)
    months = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, default='initializing', choices=[('initializing','Initializing'),('pending','Pending'),('success','Success'),('failed','Failed'),('review','Review required')])
    authorization_url = models.URLField(max_length=500, blank=True)
    provider_id = models.CharField(max_length=100, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['invoice'], condition=models.Q(invoice__isnull=False, status__in=['initializing', 'pending']), name='one_open_invoice_checkout'),
            models.UniqueConstraint(fields=['school', 'request_key'],
                condition=~models.Q(request_key=''), name='unique_school_payment_order_request_key'),
            models.CheckConstraint(check=models.Q(invoice__isnull=True) | models.Q(kind='subscription'), name='invoice_subscription_only'),
        ]


class PaymentException(models.Model):
    TYPES = [('refund', 'Refund request'), ('duplicate', 'Suspected duplicate'),
             ('incorrect', 'Incorrect payment'), ('provider', 'Provider discrepancy'),
             ('manual', 'Manual review')]
    STATES = [(value, value.replace('_', ' ').title()) for value in
              ('requested', 'under_review', 'approved', 'rejected', 'provider_pending',
               'provider_failed', 'resolved')]
    order = models.ForeignKey(PaymentOrder, on_delete=models.PROTECT, related_name='exceptions')
    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT)
    kind = models.CharField(max_length=20, choices=TYPES)
    status = models.CharField(max_length=20, choices=STATES, default='requested')
    reason = models.TextField(max_length=2000)
    admin_notes = models.TextField(max_length=2000, blank=True)
    provider_ref = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True)

    class Meta:
        ordering = ['-id']
        constraints = [models.UniqueConstraint(fields=['order', 'kind'], name='unique_order_exception_kind')]

