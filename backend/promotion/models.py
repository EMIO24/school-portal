from django.conf import settings
from django.db import models


class PromotionCriteria(models.Model):
    school               = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='promotion_criteria')
    class_level          = models.ForeignKey('enrollment.ClassLevel', on_delete=models.CASCADE, related_name='promotion_criteria')
    min_subjects_to_pass = models.PositiveSmallIntegerField(default=5)
    min_average_score    = models.DecimalField(max_digits=5, decimal_places=2, default=40)
    min_attendance_pct   = models.PositiveSmallIntegerField(default=50)
    auto_promote_if_met  = models.BooleanField(default=False)

    class Meta:
        unique_together = [('school', 'class_level')]

    def __str__(self):
        return f"Criteria — {self.class_level.name} | {self.school.name}"


class PromotionRecord(models.Model):
    DECISION_CHOICES = [
        ('promoted',  'Promoted'),
        ('repeated',  'Repeated'),
        ('graduated', 'Graduated'),
        ('withdrawn', 'Withdrawn'),
    ]

    student      = models.ForeignKey('enrollment.StudentProfile', on_delete=models.CASCADE, related_name='promotion_records')
    from_session = models.ForeignKey('academics.AcademicSession', on_delete=models.CASCADE, related_name='promotions_from')
    to_session   = models.ForeignKey('academics.AcademicSession', on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions_to')
    from_class   = models.ForeignKey('enrollment.ClassArm', on_delete=models.CASCADE, related_name='promotions_from')
    to_class     = models.ForeignKey('enrollment.ClassArm', on_delete=models.SET_NULL, null=True, blank=True, related_name='promotions_to')
    decision     = models.CharField(max_length=20, choices=DECISION_CHOICES)
    criteria_met = models.BooleanField(default=False)
    decided_by   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    notes        = models.TextField(blank=True)
    decided_at   = models.DateTimeField(auto_now_add=True)
    school       = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='promotion_records')

    class Meta:
        ordering = ['-decided_at']

    def __str__(self):
        return f"{self.student} — {self.decision} ({self.from_session})"
