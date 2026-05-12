from django.conf import settings
from django.db import models


class FeeCategory(models.Model):
    school         = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='fee_categories')
    name           = models.CharField(max_length=120)
    description    = models.TextField(blank=True)
    is_compulsory  = models.BooleanField(default=True)

    class Meta:
        unique_together = [('school', 'name')]
        ordering        = ['name']

    def __str__(self):
        return f"{self.name} — {self.school.name}"


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
        return f"{self.fee_category.name} / {self.class_level.name} — ₦{self.amount}"


class FeePayment(models.Model):
    METHOD_CHOICES = [
        ('cash',          'Cash'),
        ('paystack',      'Paystack'),
        ('bank_transfer', 'Bank Transfer'),
    ]

    school             = models.ForeignKey('tenants.School',                on_delete=models.CASCADE, related_name='fee_payments')
    student            = models.ForeignKey('enrollment.StudentProfile',     on_delete=models.CASCADE, related_name='fee_payments')
    fee_schedule       = models.ForeignKey(FeeSchedule,                     on_delete=models.CASCADE, related_name='payments')
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
            import datetime
            from django.db import IntegrityError, transaction
            year = self.payment_date.year if self.payment_date else datetime.date.today().year
            for attempt in range(1, 11):
                seq = (
                    FeePayment.objects
                    .filter(school=self.school, payment_date__year=year)
                    .count() + attempt
                )
                self.receipt_number = f"REC-{year}-{seq:04d}"
                try:
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    self.receipt_number = ''
            raise RuntimeError("Could not generate a unique receipt number after 10 attempts")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.receipt_number} — {self.student} ₦{self.amount_paid}"
