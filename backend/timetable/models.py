"""
backend/timetable/models.py

Models for the timetable module.
All models are tenant-scoped via school FK — never query without .filter(school=request.tenant).

Period          — configurable time slots for a school day (inc. breaks)
TimetableEntry  — a single lesson: class × subject × teacher × day × period
"""

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class Period(models.Model):
    """
    Represents one time slot in a school day.
    Break periods (lunch, assembly, etc.) are non-bookable.
    order_index controls visual position in the grid rows.
    """
    school      = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='periods'
    )
    name        = models.CharField(max_length=50)       # e.g. "Period 1", "Lunch Break"
    start_time  = models.TimeField()
    end_time    = models.TimeField()
    order_index = models.PositiveSmallIntegerField()     # determines row order in the grid
    is_break    = models.BooleanField(default=False)     # True → cannot assign lessons

    class Meta:
        ordering        = ['order_index']
        unique_together = [('school', 'order_index')]
        verbose_name    = 'Period'

    def __str__(self):
        flag = ' [Break]' if self.is_break else ''
        return f"{self.name}{flag} ({self.start_time:%H:%M}–{self.end_time:%H:%M})"

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({'end_time': _('End time must be after start time.')})


class TimetableEntry(models.Model):
    """
    A single scheduled lesson slot.

    Conflict rules (enforced in both clean() and the serializer):
      1. HARD BLOCK  — teacher already in another class for same day+period+term
      2. SOFT WARNING — teacher has >5 periods on the same day (non-blocking)

    The unique_together on (class_arm, day_of_week, period, term) prevents
    a class from having two subjects in the same slot.
    """

    class Day(models.TextChoices):
        MON = 'MON', _('Monday')
        TUE = 'TUE', _('Tuesday')
        WED = 'WED', _('Wednesday')
        THU = 'THU', _('Thursday')
        FRI = 'FRI', _('Friday')

    school    = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='timetable_entries'
    )
    term      = models.ForeignKey(
        'academics.Term', on_delete=models.CASCADE, related_name='timetable_entries'
    )
    class_arm = models.ForeignKey(
        'enrollment.ClassArm', on_delete=models.CASCADE, related_name='timetable_entries'
    )
    subject   = models.ForeignKey(
        'enrollment.Subject', on_delete=models.CASCADE, related_name='timetable_entries'
    )
    teacher   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='timetable_entries',
        limit_choices_to={'role': 'teacher'},
    )
    day_of_week = models.CharField(max_length=3, choices=Day.choices)
    period      = models.ForeignKey(
        Period, on_delete=models.CASCADE, related_name='timetable_entries'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # A class arm can only have one subject per slot per term
        unique_together = [('class_arm', 'day_of_week', 'period', 'term')]
        ordering        = ['day_of_week', 'period__order_index']
        verbose_name    = 'Timetable Entry'
        verbose_name_plural = 'Timetable Entries'

    def __str__(self):
        return (
            f"{self.class_arm} | {self.get_day_of_week_display()} "
            f"| {self.period.name} | {self.subject}"
        )

    def clean(self):
        """
        Model-level teacher double-booking guard.
        The serializer mirrors this so the API surface returns clear field errors.
        """
        if not all([self.teacher_id, self.day_of_week, self.period_id, self.term_id]):
            return

        conflict = (
            TimetableEntry.objects
            .filter(
                school=self.school,
                teacher_id=self.teacher_id,
                day_of_week=self.day_of_week,
                period_id=self.period_id,
                term_id=self.term_id,
            )
            .exclude(pk=self.pk)
            .select_related('class_arm')
            .first()
        )

        if conflict:
            raise ValidationError({
                'teacher': _(
                    '%(name)s is already assigned to %(class)s '
                    'during %(day)s %(period)s this term.'
                ) % {
                    'name':   self.teacher.get_full_name(),
                    'class':  conflict.class_arm,
                    'day':    self.get_day_of_week_display(),
                    'period': self.period.name,
                }
            })


class LessonRecord(models.Model):
    """One explicit outcome for a dated timetable slot; absence means unresolved."""

    class Outcome(models.TextChoices):
        DELIVERED = 'delivered', 'Delivered'
        MISSED = 'missed', 'Missed'
        CANCELLED = 'cancelled', 'Cancelled'
        SUBSTITUTED = 'substituted', 'Substituted'

    school = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='lesson_records')
    timetable_entry = models.ForeignKey(TimetableEntry, null=True, blank=True, on_delete=models.SET_NULL, related_name='lesson_records')
    # Stable even when an administrator deletes the recurring timetable entry.
    slot_id = models.PositiveBigIntegerField()
    date = models.DateField()
    term = models.ForeignKey('academics.Term', null=True, on_delete=models.SET_NULL)
    term_name = models.CharField(max_length=80)
    class_arm_id_snapshot = models.PositiveBigIntegerField()
    class_name = models.CharField(max_length=160)
    subject_id_snapshot = models.PositiveBigIntegerField()
    subject_name = models.CharField(max_length=160)
    period_name = models.CharField(max_length=50)
    period_start = models.TimeField()
    period_end = models.TimeField()
    scheduled_teacher_id = models.PositiveBigIntegerField(null=True, blank=True)
    scheduled_teacher_name = models.CharField(max_length=160, blank=True)
    actual_teacher = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='delivered_lesson_records')
    actual_teacher_name = models.CharField(max_length=160, blank=True)
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    note = models.CharField(max_length=500, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='recorded_lesson_records')
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['school', 'slot_id', 'date'], name='unique_lesson_slot_date')]
        indexes = [models.Index(fields=['school', 'date', 'outcome'])]
