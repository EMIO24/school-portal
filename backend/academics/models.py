"""
academics/models.py

Academic Calendar models:  AcademicSession → Term → Holiday

Key invariant (enforced in save(), NOT just the API):
  - Exactly one AcademicSession per school may have is_current=True
  - Exactly one Term per school may have is_current=True
  Both are enforced via database-level UPDATE before saving the new record,
  wrapped in a transaction so there is never a window with two current rows.
"""

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Q
from django.core.exceptions import ValidationError


class AcademicSession(models.Model):
    """
    Represents a full academic year, e.g. '2024/2025'.
    Multiple sessions per school; only one is 'current' at a time.
    """

    school      = models.ForeignKey(
        "tenants.School",
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    name        = models.CharField(
        max_length=20,
        help_text="e.g. '2024/2025'",
    )
    start_date  = models.DateField()
    end_date    = models.DateField()
    is_current  = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name         = "Academic Session"
        verbose_name_plural  = "Academic Sessions"
        ordering             = ["-start_date"]
        constraints          = [
            models.UniqueConstraint(
                fields=["school", "name"],
                name="unique_session_name_per_school",
            ),
            models.UniqueConstraint(
                fields=["school"],
                condition=Q(is_current=True),
                name="one_current_academic_session_per_school",
            ),
        ]

    # ── Current-session enforcement ────────────────────────────────────────

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        If this session is being marked current, atomically clear the flag
        on all other sessions for the same school before saving.
        """
        if self.school_id:
            from tenants.models import School
            School.objects.select_for_update().get(pk=self.school_id)
        if self.is_current:
            AcademicSession.objects.filter(
                school_id=self.school_id,
                is_current=True,
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    # ── Validation ─────────────────────────────────────────────────────────

    def clean(self):
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError(
                {"end_date": "End date must be after start date."}
            )

    def __str__(self):
        flag = " ✓" if self.is_current else ""
        return f"{self.name}{flag} — {self.school.name}"


# ── Term ───────────────────────────────────────────────────────────────────

class Term(models.Model):
    """
    One of three terms within an AcademicSession.
    The is_current flag is school-scoped (not session-scoped) so the
    system always knows which single term is active right now.
    """

    TERM_CHOICES = [
        ("first",  "First Term"),
        ("second", "Second Term"),
        ("third",  "Third Term"),
    ]

    session          = models.ForeignKey(
        AcademicSession,
        on_delete=models.CASCADE,
        related_name="terms",
    )
    name             = models.CharField(max_length=10, choices=TERM_CHOICES)
    start_date       = models.DateField()
    end_date         = models.DateField()
    is_current       = models.BooleanField(default=False, db_index=True)
    next_term_begins = models.DateField(
        null=True,
        blank=True,
        help_text="First day of next term — shown on result sheets.",
    )

    class Meta:
        verbose_name        = "Term"
        verbose_name_plural = "Terms"
        ordering            = ["session__start_date", "name"]
        constraints         = [
            models.UniqueConstraint(
                fields=["session", "name"],
                name="unique_term_per_session",
            )
        ]

    # ── Current-term enforcement ───────────────────────────────────────────

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        If this term is being marked current, clear the flag on all other
        terms belonging to the SAME SCHOOL (across all sessions).
        """
        if self.session_id:
            from tenants.models import School
            School.objects.select_for_update().get(pk=self.session.school_id)
        if self.is_current:
            Term.objects.filter(
                session__school_id=self.session.school_id,
                is_current=True,
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    # ── Validation ─────────────────────────────────────────────────────────

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            errors["end_date"] = "End date must be after start date."
        if self.start_date and self.session_id and self.start_date < self.session.start_date:
            errors["start_date"] = "Term start date cannot be before the session start date."
        if self.end_date and self.session_id and self.end_date > self.session.end_date:
            errors["end_date"] = "Term end date cannot be after the session end date."
        if self.next_term_begins and self.end_date and self.next_term_begins <= self.end_date:
            errors["next_term_begins"] = "Next term must begin after this term ends."
        if errors:
            raise ValidationError(errors)

    @property
    def school(self):
        return self.session.school

    def get_name_display_short(self):
        return {"first": "1st", "second": "2nd", "third": "3rd"}.get(self.name, self.name)

    def __str__(self):
        flag = " ✓" if self.is_current else ""
        return f"{self.get_name_display()} — {self.session.name}{flag}"


class AcademicRollover(models.Model):
    """Auditable school-year cutover state. Execution is introduced in later 19E stages."""

    STATUS_CHOICES = [
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    school = models.ForeignKey(
        "tenants.School", on_delete=models.PROTECT, related_name="academic_rollovers"
    )
    source_session = models.ForeignKey(
        AcademicSession, on_delete=models.PROTECT, related_name="rollovers_from"
    )
    destination_session = models.ForeignKey(
        AcademicSession, on_delete=models.PROTECT, related_name="rollovers_to"
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="preparing", db_index=True)
    preview_snapshot = models.JSONField(default=dict, blank=True)
    configuration_options = models.JSONField(default=dict, blank=True)
    student_count = models.PositiveIntegerField(default=0)
    promoted_count = models.PositiveIntegerField(default=0)
    repeated_count = models.PositiveIntegerField(default=0)
    graduated_count = models.PositiveIntegerField(default=0)
    withdrawn_count = models.PositiveIntegerField(default=0)
    idempotency_key = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_academic_rollovers",
    )
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="completed_academic_rollovers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["school", "source_session", "destination_session"],
                condition=Q(status="completed"),
                name="one_completed_rollover_per_session_pair",
            ),
            models.UniqueConstraint(
                fields=["school", "idempotency_key"],
                condition=~Q(idempotency_key=""),
                name="unique_school_rollover_idempotency_key",
            ),
            models.CheckConstraint(
                condition=~Q(source_session=F("destination_session")),
                name="rollover_sessions_must_differ",
            ),
        ]

    def clean(self):
        errors = {}
        if self.source_session_id and self.source_session.school_id != self.school_id:
            errors["source_session"] = "Source session must belong to this school."
        if self.destination_session_id and self.destination_session.school_id != self.school_id:
            errors["destination_session"] = "Destination session must belong to this school."
        if self.source_session_id and self.destination_session_id:
            if self.destination_session.start_date <= self.source_session.end_date:
                errors["destination_session"] = "Destination session must begin after the source session ends."
        if self.status == "completed" and not self.completed_at:
            errors["completed_at"] = "A completed rollover requires a completion timestamp."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.school} — {self.source_session.name} → {self.destination_session.name} ({self.status})"


# ── Holiday ────────────────────────────────────────────────────────────────

class Holiday(models.Model):
    """
    A named break/holiday within a Term.
    Used for timetable display and CBT scheduling exclusions.
    """

    HOLIDAY_TYPE_CHOICES = [
        ("public",     "Public Holiday"),
        ("school",     "School Holiday"),
        ("exam_break", "Exam Break"),
    ]

    term         = models.ForeignKey(
        Term,
        on_delete=models.CASCADE,
        related_name="holidays",
    )
    name         = models.CharField(max_length=150)
    start_date   = models.DateField()
    end_date     = models.DateField()
    holiday_type = models.CharField(
        max_length=20,
        choices=HOLIDAY_TYPE_CHOICES,
        default="public",
    )

    class Meta:
        verbose_name        = "Holiday"
        verbose_name_plural = "Holidays"
        ordering            = ["start_date"]

    def clean(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(
                {"end_date": "End date cannot be before start date."}
            )

    @property
    def school(self):
        return self.term.session.school

    def __str__(self):
        return f"{self.name} ({self.start_date} → {self.end_date})"