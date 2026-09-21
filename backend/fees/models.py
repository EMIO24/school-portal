from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


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
    recorded_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='recorded_payments',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import uuid
            self.receipt_number = 'REC-' + uuid.uuid4().hex[:26].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} â€” {self.student} â‚¦{self.amount_paid}"


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


class TermInvoice(models.Model):
    INVOICE_STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]

    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT, related_name='term_invoices')
    plan = models.CharField(max_length=20, choices=[('free', 'Free'), ('basic', 'Basic'), ('premium', 'Premium'), ('enterprise', 'Enterprise')], default='premium')
    academic_session = models.ForeignKey('academics.AcademicSession', on_delete=models.PROTECT, related_name='term_invoices')
    term = models.ForeignKey('academics.Term', on_delete=models.PROTECT, related_name='term_invoices')
    active_student_count = models.PositiveIntegerField(default=0)
    snapshot_date = models.DateField()
    standard_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_eligible = models.BooleanField(default=False)
    discount_percentage = models.PositiveSmallIntegerField(default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    effective_rate = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    final_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    invoice_number = models.CharField(max_length=60, unique=True, blank=True)
    issue_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS_CHOICES, default='issued')
    paid_date = models.DateTimeField(null=True, blank=True)
    grace_period_days = models.PositiveSmallIntegerField(default=14)
    notes = models.TextField(blank=True)
    audit_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['school', 'academic_session', 'term'], name='unique_term_invoice_per_school_term'),
        ]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            prefix = 'INV'
            self.invoice_number = f'{prefix}-{self.issue_date.year}-{self.pk or "NEW"}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} — {self.school.name} ({self.term})"


class PaymentOrder(models.Model):
    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT, related_name='payment_orders')
    payer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    student = models.ForeignKey('enrollment.StudentProfile', on_delete=models.PROTECT, null=True, blank=True)
    kind = models.CharField(max_length=20, choices=[('fees', 'School fees'), ('subscription', 'Portal subscription')])
    reference = models.CharField(max_length=100, unique=True)
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

