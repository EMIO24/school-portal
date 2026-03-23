"""
backend/attendance/models.py

Attendance tracking models for the multi-tenant Nigerian school portal.

Design decisions:
  - AttendanceSession represents ONE marking event (daily or per-period).
  - AttendanceRecord is a per-student row within that session.
  - is_finalized locks the session — no further edits allowed.
  - Attendance percentage helpers live on the queryset/manager so they
    can be computed efficiently with aggregates instead of per-object Python loops.
  - School-level mode setting (daily vs per_period) is stored on School.settings
    JSONField; the session's own mode field records what was actually used.
"""

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q


# ─────────────────────────────────────────────────────────────────────────────
# Managers
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceRecordQuerySet(models.QuerySet):

    def for_student_term(self, student_id, term_id):
        """All records for a student in a term (across all sessions)."""
        return self.filter(
            student_id=student_id,
            attendance_session__term_id=term_id,
        )

    def attendance_summary(self, student_id, term_id):
        """
        Returns a dict:
          { total, present, absent, late, excused, percentage }
        """
        qs = self.for_student_term(student_id, term_id)
        agg = qs.aggregate(
            total    = Count('id'),
            present  = Count('id', filter=Q(status='present')),
            absent   = Count('id', filter=Q(status='absent')),
            late     = Count('id', filter=Q(status='late')),
            excused  = Count('id', filter=Q(status='excused')),
        )
        total = agg['total'] or 0
        # Late counts as present for the % calculation (Nigerian convention)
        effective_present = (agg['present'] or 0) + (agg['late'] or 0)
        agg['percentage'] = round(effective_present / total * 100, 1) if total else 0.0
        return agg


class AttendanceRecordManager(models.Manager):
    def get_queryset(self):
        return AttendanceRecordQuerySet(self.model, using=self._db)

    def summary(self, student_id, term_id):
        return self.get_queryset().attendance_summary(student_id, term_id)


# ─────────────────────────────────────────────────────────────────────────────
# AttendanceSession
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceSession(models.Model):
    """
    A single attendance-marking event.

    Daily mode   → period is NULL, one session per class per day.
    Per-period   → period is set, one session per class per period per day.

    is_finalized → teacher has locked the session; no PATCH/submit allowed.
    """

    class Mode(models.TextChoices):
        DAILY      = 'daily',      _('Daily')
        PER_PERIOD = 'per_period', _('Per Period')

    school    = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='attendance_sessions'
    )
    class_arm = models.ForeignKey(
        'enrollment.ClassArm', on_delete=models.CASCADE, related_name='attendance_sessions'
    )
    teacher   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name='attendance_sessions',
        limit_choices_to={'role': 'teacher'},
    )
    term      = models.ForeignKey(
        'academics.Term', on_delete=models.CASCADE, related_name='attendance_sessions'
    )
    date      = models.DateField()
    period    = models.ForeignKey(
        'timetable.Period', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendance_sessions',
        help_text='Only set in per-period mode.',
    )
    mode         = models.CharField(max_length=10, choices=Mode.choices, default=Mode.DAILY)
    is_finalized = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'period__order_index']
        # One daily session per class per day per term.
        # Per-period adds the period into the key via clean().
        verbose_name = 'Attendance Session'

    def __str__(self):
        period_part = f' / {self.period}' if self.period else ''
        return f"{self.class_arm} | {self.date}{period_part} | {self.mode}"

    def clean(self):
        """
        Uniqueness rules:
          daily      → (school, class_arm, term, date, mode=daily)  unique
          per_period → (school, class_arm, term, date, period)       unique
        """
        qs = AttendanceSession.objects.filter(
            school=self.school,
            class_arm=self.class_arm,
            term=self.term,
            date=self.date,
            mode=self.mode,
        ).exclude(pk=self.pk)

        if self.mode == self.Mode.PER_PERIOD:
            qs = qs.filter(period=self.period)
        else:
            qs = qs.filter(period__isnull=True)

        if qs.exists():
            raise ValidationError(
                _('An attendance session already exists for this class on this date.')
            )


# ─────────────────────────────────────────────────────────────────────────────
# AttendanceRecord
# ─────────────────────────────────────────────────────────────────────────────

class AttendanceRecord(models.Model):
    """
    One row per student per AttendanceSession.

    Status meanings (Nigerian schools convention):
      P = present          → counts toward attendance %
      A = absent           → does not count
      L = late             → counts as present for % but flagged
      E = excused absence  → does not count against student
    """

    class Status(models.TextChoices):
        PRESENT  = 'present',  _('Present')
        ABSENT   = 'absent',   _('Absent')
        LATE     = 'late',     _('Late')
        EXCUSED  = 'excused',  _('Excused')

    attendance_session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name='records'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='attendance_records',
        limit_choices_to={'role': 'student'},
    )
    status  = models.CharField(max_length=8, choices=Status.choices, default=Status.PRESENT)
    remark  = models.CharField(max_length=255, blank=True, default='')

    objects = AttendanceRecordManager()

    class Meta:
        unique_together = [('attendance_session', 'student')]
        ordering        = ['student__last_name', 'student__first_name']
        verbose_name    = 'Attendance Record'

    def __str__(self):
        return f"{self.student} | {self.attendance_session.date} | {self.status}"