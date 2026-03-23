"""
backend/gradebook/models.py

Nigerian secondary school gradebook models.

Grading structure:
  CA (40%)  = first_test + second_test + assignment + project + practical
  Exam (60%) = exam_score
  Total      = ca_total + exam_score  (0–100)
  Grade      = looked up from GradeScale (A1–F9, WAEC standard)

Domain models:
  AffectiveDomain   — character/behavioural traits rated 1–5
  PsychomotorDomain — physical/creative skills rated 1–5

All FKs use settings.AUTH_USER_MODEL and the correct app labels
confirmed from the project structure.
"""

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────────────────────────────────────
# Grade Scale
# ─────────────────────────────────────────────────────────────────────────────

class GradeScale(models.Model):
    """
    Maps a score range to a WAEC grade letter and remark.
    One set per school — seeded from DEFAULT_NIGERIAN_SCALE on school creation.
    """

    class Grade(models.TextChoices):
        A1 = 'A1', 'A1'
        B2 = 'B2', 'B2'
        B3 = 'B3', 'B3'
        C4 = 'C4', 'C4'
        C5 = 'C5', 'C5'
        C6 = 'C6', 'C6'
        D7 = 'D7', 'D7'
        E8 = 'E8', 'E8'
        F9 = 'F9', 'F9'

    class Remark(models.TextChoices):
        EXCELLENT  = 'Excellent',   _('Excellent')
        VERY_GOOD  = 'Very Good',   _('Very Good')
        GOOD       = 'Good',        _('Good')
        CREDIT     = 'Credit',      _('Credit')
        PASS       = 'Pass',        _('Pass')
        FAIL       = 'Fail',        _('Fail')

    school    = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='grade_scales'
    )
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    grade     = models.CharField(max_length=2, choices=Grade.choices)
    remark    = models.CharField(max_length=20, choices=Remark.choices)

    class Meta:
        ordering        = ['-min_score']
        unique_together = [('school', 'grade')]
        verbose_name    = 'Grade Scale'

    def __str__(self):
        return f"{self.grade} ({self.min_score}–{self.max_score}) — {self.remark}"


# Default Nigerian WAEC grading scale — seeded per school on creation
DEFAULT_NIGERIAN_SCALE = [
    {'min_score': 75, 'max_score': 100, 'grade': 'A1', 'remark': 'Excellent'},
    {'min_score': 70, 'max_score': 74,  'grade': 'B2', 'remark': 'Very Good'},
    {'min_score': 65, 'max_score': 69,  'grade': 'B3', 'remark': 'Good'},
    {'min_score': 60, 'max_score': 64,  'grade': 'C4', 'remark': 'Credit'},
    {'min_score': 55, 'max_score': 59,  'grade': 'C5', 'remark': 'Credit'},
    {'min_score': 50, 'max_score': 54,  'grade': 'C6', 'remark': 'Credit'},
    {'min_score': 45, 'max_score': 49,  'grade': 'D7', 'remark': 'Pass'},
    {'min_score': 40, 'max_score': 44,  'grade': 'E8', 'remark': 'Pass'},
    {'min_score':  0, 'max_score': 39,  'grade': 'F9', 'remark': 'Fail'},
]


@receiver(post_save, sender='tenants.School')
def seed_grade_scale(sender, instance, created, **kwargs):
    """Auto-seed the default Nigerian WAEC grade scale for every new school."""
    if created:
        GradeScale.objects.bulk_create([
            GradeScale(school=instance, **row)
            for row in DEFAULT_NIGERIAN_SCALE
        ])


# ─────────────────────────────────────────────────────────────────────────────
# Score Entry
# ─────────────────────────────────────────────────────────────────────────────

def _decimal(val):
    """Coerce to 2dp Decimal for score fields."""
    return Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class ScoreEntry(models.Model):
    """
    One row per student × subject × term × session.

    CA breakdown (40 marks total):
        first_test   — max configurable, default 10
        second_test  — max configurable, default 10
        assignment   — max configurable, default 10
        project      — max configurable, default  5
        practical    — max configurable, default  5
        ca_total     = sum of above (computed, saved to DB for query performance)

    Exam (60 marks), Total (100).
    Grade and remark are denormalised from GradeScale for fast broadsheet queries.
    """

    school    = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='score_entries'
    )
    student   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='score_entries', limit_choices_to={'role': 'student'}
    )
    subject   = models.ForeignKey(
        'enrollment.Subject', on_delete=models.CASCADE, related_name='score_entries'
    )
    class_arm = models.ForeignKey(
        'enrollment.ClassArm', on_delete=models.CASCADE, related_name='score_entries'
    )
    session   = models.ForeignKey(
        'academics.AcademicSession', on_delete=models.CASCADE, related_name='score_entries'
    )
    term      = models.ForeignKey(
        'academics.Term', on_delete=models.CASCADE, related_name='score_entries'
    )
    teacher   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='graded_entries', limit_choices_to={'role': 'teacher'}
    )

    # ── CA sub-components ────────────────────────────────────────────────────
    # Each stored as decimal so partial marks work (e.g. 8.5/10)
    _score_field = dict(
        max_digits=5, decimal_places=2, default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    first_test   = models.DecimalField(**_score_field)
    second_test  = models.DecimalField(**_score_field)
    assignment   = models.DecimalField(**_score_field)
    project      = models.DecimalField(**_score_field)
    practical    = models.DecimalField(**_score_field)

    # Denormalised sum — recomputed on every save()
    ca_total     = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))

    # ── Exam ─────────────────────────────────────────────────────────────────
    exam_score   = models.DecimalField(**_score_field)

    # Denormalised total — recomputed on every save()
    total_score  = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))

    # ── Grade (denormalised from GradeScale) ──────────────────────────────────
    grade        = models.CharField(max_length=2,  blank=True, default='')
    remark       = models.CharField(max_length=20, blank=True, default='')

    is_published = models.BooleanField(default=False)

    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('student', 'subject', 'term', 'session', 'school')]
        ordering        = ['student__last_name', 'student__first_name']
        verbose_name    = 'Score Entry'
        verbose_name_plural = 'Score Entries'

    def __str__(self):
        return f"{self.student} | {self.subject} | {self.term} | {self.total_score}"

    # ── Computed helpers ──────────────────────────────────────────────────────

    @property
    def computed_ca(self):
        return (
            (self.first_test  or Decimal('0'))
            + (self.second_test or Decimal('0'))
            + (self.assignment  or Decimal('0'))
            + (self.project     or Decimal('0'))
            + (self.practical   or Decimal('0'))
        )

    @property
    def computed_total(self):
        return self.computed_ca + (self.exam_score or Decimal('0'))

    def resolve_grade(self):
        """Look up grade + remark from the school's GradeScale."""
        total = self.computed_total
        band  = (
            GradeScale.objects
            .filter(school=self.school, min_score__lte=total, max_score__gte=total)
            .first()
        )
        if band:
            return band.grade, band.remark
        return 'F9', 'Fail'

    def save(self, *args, **kwargs):
        # Recompute denormalised fields before every save
        self.ca_total    = _decimal(self.computed_ca)
        self.total_score = _decimal(self.computed_total)
        self.grade, self.remark = self.resolve_grade()
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Domain rating helpers
# ─────────────────────────────────────────────────────────────────────────────

RATING_FIELD = dict(
    default=3,
    validators=[MinValueValidator(1), MaxValueValidator(5)]
)


class AffectiveDomain(models.Model):
    """
    Character and behavioural trait ratings for a student in a term.
    Rated 1 (Poor) → 5 (Excellent).
    """
    school    = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='affective_domains'
    )
    student   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='affective_domains', limit_choices_to={'role': 'student'}
    )
    class_arm = models.ForeignKey(
        'enrollment.ClassArm', on_delete=models.CASCADE, related_name='affective_domains'
    )
    term      = models.ForeignKey(
        'academics.Term', on_delete=models.CASCADE, related_name='affective_domains'
    )

    # Traits
    punctuality            = models.IntegerField(**RATING_FIELD)
    neatness               = models.IntegerField(**RATING_FIELD)
    honesty                = models.IntegerField(**RATING_FIELD)
    attentiveness          = models.IntegerField(**RATING_FIELD)
    relationship_with_others = models.IntegerField(**RATING_FIELD)
    leadership             = models.IntegerField(**RATING_FIELD)
    creativity             = models.IntegerField(**RATING_FIELD)
    sport_games            = models.IntegerField(**RATING_FIELD)
    handling_of_tools      = models.IntegerField(**RATING_FIELD)

    class Meta:
        unique_together = [('student', 'term', 'school')]
        verbose_name    = 'Affective Domain'

    def __str__(self):
        return f"Affective | {self.student} | {self.term}"


class PsychomotorDomain(models.Model):
    """
    Physical and creative skill ratings for a student in a term.
    Rated 1 (Poor) → 5 (Excellent).
    """
    school    = models.ForeignKey(
        'tenants.School', on_delete=models.CASCADE, related_name='psychomotor_domains'
    )
    student   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='psychomotor_domains', limit_choices_to={'role': 'student'}
    )
    class_arm = models.ForeignKey(
        'enrollment.ClassArm', on_delete=models.CASCADE, related_name='psychomotor_domains'
    )
    term      = models.ForeignKey(
        'academics.Term', on_delete=models.CASCADE, related_name='psychomotor_domains'
    )

    # Skills
    handwriting    = models.IntegerField(**RATING_FIELD)
    drawing        = models.IntegerField(**RATING_FIELD)
    verbal_fluency = models.IntegerField(**RATING_FIELD)
    musical_skills = models.IntegerField(**RATING_FIELD)

    class Meta:
        unique_together = [('student', 'term', 'school')]
        verbose_name    = 'Psychomotor Domain'

    def __str__(self):
        return f"Psychomotor | {self.student} | {self.term}"