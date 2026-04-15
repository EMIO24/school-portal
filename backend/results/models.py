"""
backend/results/models.py

ResultRemark stores per-student per-term remarks and the computed class position.
Positions are calculated server-side via compute_positions() and written here.

All FKs use correct project app labels (tenants, enrollment, academics, settings.AUTH_USER_MODEL).
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ResultRemark(models.Model):
    """
    Stores remarks and class position for a student in a term.
    Created on demand — one row per student per term per school.
    """
    school    = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='result_remarks'
    )
    student   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='result_remarks', limit_choices_to={'role': 'student'}
    )
    term      = models.ForeignKey(
        'academics.Term', on_delete=models.CASCADE, related_name='result_remarks'
    )
    class_arm = models.ForeignKey(
        'enrollment.ClassArm', on_delete=models.CASCADE,
        related_name='result_remarks', null=True, blank=True
    )

    # Editable by class teacher and principal
    class_teacher_remark = models.TextField(blank=True, default='')
    principal_remark     = models.TextField(blank=True, default='')

    # Computed server-side by compute_positions view action
    computed_position = models.PositiveIntegerField(null=True, blank=True)

    # Cached aggregates written at position-compute time for fast broadsheet queries
    total_score = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        help_text='Sum of all subject totals for this student in this term.'
    )
    average_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='Average score across all subjects.'
    )
    subjects_offered = models.PositiveSmallIntegerField(
        default=0,
        help_text='Number of subjects with a published score entry.'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('student', 'term', 'school')]
        ordering        = ['computed_position', 'student__last_name']
        verbose_name    = 'Result Remark'

    def __str__(self):
        pos = f' | #{self.computed_position}' if self.computed_position else ''
        return f"{self.student} | {self.term}{pos}"