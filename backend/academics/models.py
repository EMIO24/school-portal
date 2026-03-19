"""
academics/models.py

Academic Calendar models:  AcademicSession → Term → Holiday

Key invariant (enforced in save(), NOT just the API):
  - Exactly one AcademicSession per school may have is_current=True
  - Exactly one Term per school may have is_current=True
  Both are enforced via database-level UPDATE before saving the new record,
  wrapped in a transaction so there is never a window with two current rows.
"""

from django.db import models, transaction
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
            )
        ]

    # ── Current-session enforcement ────────────────────────────────────────

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        If this session is being marked current, atomically clear the flag
        on all other sessions for the same school before saving.
        """
        if self.is_current:
            AcademicSession.objects.filter(
                school=self.school,
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
        if self.is_current:
            Term.objects.filter(
                session__school=self.session.school,
                is_current=True,
            ).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    # ── Validation ─────────────────────────────────────────────────────────

    def clean(self):
        errors = {}
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            errors["end_date"] = "End date must be after start date."
        if (self.start_date and self.session_id and
                self.start_date < self.session.start_date):
            errors["start_date"] = (
                "Term start date cannot be before the session start date."
            )
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