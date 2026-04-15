"""
backend/results/models.py

ResultRemark stores per-student per-term remarks and the computed class position.
Positions are calculated server-side via compute_positions() and written here.

All FKs use correct project app labels (tenants, enrollment, academics, settings.AUTH_USER_MODEL).
"""

import random
import string

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


def _generate_serial(school_slug):
    """Generate a serial number in the format {SLUG}-XXXX-XXXX (uppercase alphanumeric)."""
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=4))
    return f"{school_slug.upper()}-{part1}-{part2}"


class ScratchCard(models.Model):
    """
    Single-use PIN card for public result checking.
    Admin generates batches; plain PINs are returned once as CSV for printing.
    The PIN is stored hashed (Django's make_password) — never retrievable again.
    """
    school         = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='scratch_cards'
    )
    serial_number  = models.CharField(max_length=30, unique=True)
    pin_hash       = models.CharField(max_length=255)
    term           = models.ForeignKey(
        'academics.Term', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='scratch_cards'
    )
    batch_name     = models.CharField(max_length=100)
    price          = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    generated_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='generated_scratch_cards'
    )

    is_used        = models.BooleanField(default=False)
    used_at        = models.DateTimeField(null=True, blank=True)
    used_by_student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='used_scratch_cards',
        limit_choices_to={'role': 'student'}
    )

    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Scratch Card'

    def __str__(self):
        status = 'USED' if self.is_used else 'unused'
        return f"{self.serial_number} [{status}] — {self.batch_name}"