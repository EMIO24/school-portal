"""Issued subscription records: updates go through the guarded lifecycle service."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class InvoiceQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        if kwargs.get('update_conflicts'):
            raise ValidationError('Issued invoices cannot be overwritten.')
        return super().bulk_create(objs, **kwargs)

    def update(self, **kwargs):
        raise ValidationError('Issued invoices cannot be edited. Use the invoice lifecycle service.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('Issued invoices cannot be edited.')

    def delete(self):
        raise ValidationError('Issued invoices must be voided, not deleted.')


class TermInvoice(models.Model):
    STATES = [('issued', 'Issued'), ('paid', 'Paid'), ('void', 'Void')]
    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT)
    academic_session = models.ForeignKey('academics.AcademicSession', on_delete=models.PROTECT)
    term = models.ForeignKey('academics.Term', on_delete=models.PROTECT)
    # Snapshot labels survive later school/calendar renaming.
    school_name = models.CharField(max_length=255)
    session_name = models.CharField(max_length=20)
    term_name = models.CharField(max_length=50)
    plan = models.CharField(max_length=20)
    subscription_months = models.PositiveSmallIntegerField(null=True, blank=True)
    billing_context = models.CharField(max_length=20, default='subscription', editable=False)
    active_student_count = models.PositiveIntegerField()
    snapshot_at = models.DateTimeField(default=timezone.now, editable=False)
    standard_rate = models.DecimalField(max_digits=12, decimal_places=2)
    discount_applied = models.BooleanField()
    discount_percentage = models.PositiveSmallIntegerField()
    discount_amount = models.DecimalField(max_digits=16, decimal_places=2)
    effective_rate = models.DecimalField(max_digits=14, decimal_places=4)
    subtotal = models.DecimalField(max_digits=16, decimal_places=2)
    final_amount = models.DecimalField(max_digits=16, decimal_places=2)
    currency = models.CharField(max_length=3, default='NGN', editable=False)
    invoice_number = models.CharField(max_length=40, unique=True, editable=False)
    issue_date = models.DateField()
    due_date = models.DateField()
    grace_period_days = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATES, default='issued')
    paid_at = models.DateTimeField(null=True, blank=True)
    payment = models.OneToOneField('fees.PaymentOrder', on_delete=models.PROTECT, null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=500, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    objects = InvoiceQuerySet.as_manager()

    class Meta:
        ordering = ['-issue_date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['school', 'term', 'billing_context'], name='unique_school_term_invoice'),
            models.CheckConstraint(check=models.Q(due_date__gte=models.F('issue_date')), name='invoice_due_after_issue'),
            models.CheckConstraint(check=models.Q(final_amount__gte=0), name='invoice_nonnegative_total'),
            models.CheckConstraint(check=(
                models.Q(status='issued', paid_at__isnull=True, payment__isnull=True, voided_at__isnull=True)
                | models.Q(status='paid', paid_at__isnull=False, payment__isnull=False, voided_at__isnull=True)
                | models.Q(status='void', paid_at__isnull=True, payment__isnull=True, voided_at__isnull=False)
            ), name='invoice_valid_lifecycle'),
        ]
        indexes = [models.Index(fields=['school', 'status', 'due_date'])]

    @property
    def display_status(self):
        if self.status == 'issued' and self.due_date < timezone.localdate():
            return 'overdue'
        return self.status

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Issued invoices cannot be edited. Use the invoice lifecycle service.')
        kwargs['force_insert'] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Issued invoices must be voided, not deleted.')
