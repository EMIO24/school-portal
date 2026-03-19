"""
enrollment/models.py

School structure + student enrollment models.

Hierarchy:
  School → ClassLevel (JSS1..SS3) → ClassArm (JSS1A, JSS1B…)
  StudentProfile → ClassArm (current_class)
  Subject → ClassLevel (M2M: subject taught to which levels)

Admission number format: SLUG-YYYY-XXXX  e.g. GHS-2024-0042
Generated in utils.py, assigned in StudentProfile.save() on first create.
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.core.exceptions import ValidationError

User = get_user_model()


# ── ClassLevel ─────────────────────────────────────────────────────────────

class ClassLevel(models.Model):
    """
    e.g. JSS1, JSS2, JSS3, SS1, SS2, SS3
    order_index drives display order and report card sorting.
    """

    LEVEL_CHOICES = [
        ("JSS1", "JSS 1"),
        ("JSS2", "JSS 2"),
        ("JSS3", "JSS 3"),
        ("SS1",  "SS 1"),
        ("SS2",  "SS 2"),
        ("SS3",  "SS 3"),
    ]

    school      = models.ForeignKey(
        "tenants.School",
        on_delete=models.CASCADE,
        related_name="class_levels",
    )
    name        = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    order_index = models.PositiveSmallIntegerField(
        default=0,
        help_text="Ascending order for display (0 = JSS1 first).",
    )

    class Meta:
        verbose_name        = "Class Level"
        verbose_name_plural = "Class Levels"
        ordering            = ["order_index", "name"]
        constraints         = [
            models.UniqueConstraint(
                fields=["school", "name"],
                name="unique_class_level_per_school",
            )
        ]

    def __str__(self):
        return f"{self.name} — {self.school.name}"


# ── ClassArm ───────────────────────────────────────────────────────────────

class ClassArm(models.Model):
    """
    A physical class: JSS1A, SS2B, etc.
    class_teacher is optional — a class may not yet have one assigned.
    """

    school        = models.ForeignKey(
        "tenants.School",
        on_delete=models.CASCADE,
        related_name="class_arms",
    )
    class_level   = models.ForeignKey(
        ClassLevel,
        on_delete=models.CASCADE,
        related_name="arms",
    )
    name          = models.CharField(
        max_length=10,
        help_text="Arm letter(s), e.g. 'A', 'B', 'Gold'",
    )
    class_teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="homeroom_classes",
        limit_choices_to={"role": "teacher"},
    )

    class Meta:
        verbose_name        = "Class Arm"
        verbose_name_plural = "Class Arms"
        ordering            = ["class_level__order_index", "name"]
        constraints         = [
            models.UniqueConstraint(
                fields=["school", "class_level", "name"],
                name="unique_arm_per_level_per_school",
            )
        ]

    @property
    def full_name(self):
        """e.g. 'JSS1A'"""
        return f"{self.class_level.name}{self.name}"

    def __str__(self):
        return f"{self.full_name} — {self.school.name}"


# ── Subject ────────────────────────────────────────────────────────────────

class Subject(models.Model):
    """
    A subject offered by the school.
    M2M to ClassLevel: a subject may be taught to multiple levels.
    CA/Exam max scores are configurable per subject (default 40/60).
    """

    CATEGORY_CHOICES = [
        ("core",       "Core"),
        ("elective",   "Elective"),
        ("vocational", "Vocational"),
    ]

    school          = models.ForeignKey(
        "tenants.School",
        on_delete=models.CASCADE,
        related_name="subjects",
    )
    name            = models.CharField(max_length=100)
    code            = models.CharField(
        max_length=10,
        help_text="Short code, e.g. ENG, MTH, PHY",
    )
    class_levels    = models.ManyToManyField(
        ClassLevel,
        blank=True,
        related_name="subjects",
        help_text="Which class levels this subject is offered to.",
    )
    category        = models.CharField(
        max_length=15,
        choices=CATEGORY_CHOICES,
        default="core",
    )
    max_ca_score    = models.PositiveSmallIntegerField(
        default=40,
        help_text="Maximum continuous assessment score (default 40).",
    )
    max_exam_score  = models.PositiveSmallIntegerField(
        default=60,
        help_text="Maximum examination score (default 60).",
    )

    class Meta:
        verbose_name        = "Subject"
        verbose_name_plural = "Subjects"
        ordering            = ["name"]
        constraints         = [
            models.UniqueConstraint(
                fields=["school", "code"],
                name="unique_subject_code_per_school",
            )
        ]

    @property
    def max_total(self):
        return self.max_ca_score + self.max_exam_score

    def clean(self):
        if self.max_ca_score + self.max_exam_score != 100:
            raise ValidationError(
                "max_ca_score + max_exam_score must equal 100."
            )

    def __str__(self):
        return f"{self.code} — {self.name} ({self.school.name})"


# ── StudentProfile ─────────────────────────────────────────────────────────

class StudentProfile(models.Model):
    """
    Extended profile for students.
    One-to-one with accounts.CustomUser (role='student').
    """

    GENDER_CHOICES = [
        ("male",   "Male"),
        ("female", "Female"),
    ]

    STATUS_CHOICES = [
        ("active",     "Active"),
        ("graduated",  "Graduated"),
        ("withdrawn",  "Withdrawn"),
        ("suspended",  "Suspended"),
    ]

    RELATIONSHIP_CHOICES = [
        ("father",   "Father"),
        ("mother",   "Mother"),
        ("guardian", "Guardian"),
        ("sibling",  "Sibling"),
        ("other",    "Other"),
    ]

    # ── Core links ────────────────────────────────────────────────────────
    user   = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="student_profile",
        limit_choices_to={"role": "student"},
    )
    school = models.ForeignKey(
        "tenants.School",
        on_delete=models.CASCADE,
        related_name="students",
    )

    # ── Admission ─────────────────────────────────────────────────────────
    admission_number = models.CharField(
        max_length=30,
        unique=True,
        blank=True,          # generated in save()
        help_text="Auto-generated: SLUG-YYYY-XXXX",
    )
    admission_date   = models.DateField(auto_now_add=True)
    status           = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="active",
        db_index=True,
    )

    # ── Personal ──────────────────────────────────────────────────────────
    dob               = models.DateField(null=True, blank=True, verbose_name="Date of Birth")
    gender            = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    state_of_origin   = models.CharField(max_length=50, blank=True)
    religion          = models.CharField(max_length=50, blank=True)

    # ── Academic placement ────────────────────────────────────────────────
    current_class = models.ForeignKey(
        ClassArm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )

    # ── Guardian ──────────────────────────────────────────────────────────
    guardian_name         = models.CharField(max_length=150, blank=True)
    guardian_phone        = models.CharField(max_length=20, blank=True)
    guardian_email        = models.EmailField(blank=True)
    guardian_relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        blank=True,
    )

    class Meta:
        verbose_name        = "Student Profile"
        verbose_name_plural = "Student Profiles"
        ordering            = ["school", "admission_number"]
        indexes             = [
            models.Index(fields=["school", "status"]),
            models.Index(fields=["admission_number"]),
        ]

    def save(self, *args, **kwargs):
        """Auto-generate admission_number on first save."""
        if not self.admission_number:
            from .utils import generate_admission_number
            self.admission_number = generate_admission_number(self.school)
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.full_name

    def __str__(self):
        return f"{self.admission_number} — {self.full_name}"


# ── StaffProfile ───────────────────────────────────────────────────────────

class StaffProfile(models.Model):
    """
    Extended profile for school_admin and teacher roles.
    One-to-one with accounts.CustomUser.

    Staff ID format: SLUG-STAFF-XXXX  e.g.  GHS-STAFF-0007
    Generated in save() via utils.generate_staff_id().
    """

    QUALIFICATION_CHOICES = [
        ("ssce", "SSCE / WAEC"), ("nd", "ND / NCE"), ("hnd", "HND"),
        ("bsc", "B.Sc / B.Ed / BA"), ("pgd", "PGD"),
        ("msc", "M.Sc / M.Ed / MA"), ("phd", "Ph.D"), ("other", "Other"),
    ]
    EMPLOYMENT_STATUS_CHOICES = [
        ("active", "Active"), ("on_leave", "On Leave"),
        ("suspended", "Suspended"), ("terminated", "Terminated"),
        ("resigned", "Resigned"),
    ]
    GENDER_CHOICES = [("male", "Male"), ("female", "Female")]

    # ── Core links ────────────────────────────────────────────────────────
    user   = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="staff_profile",
    )
    school = models.ForeignKey(
        "tenants.School", on_delete=models.CASCADE, related_name="staff",
    )

    # ── Staff ID ──────────────────────────────────────────────────────────
    staff_id = models.CharField(
        max_length=30, unique=True, blank=True,
        help_text="Auto-generated: SLUG-STAFF-XXXX",
    )

    # ── Personal ──────────────────────────────────────────────────────────
    dob             = models.DateField(null=True, blank=True)
    gender          = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    phone           = models.CharField(max_length=20, blank=True)
    address         = models.TextField(blank=True)
    state_of_origin = models.CharField(max_length=50, blank=True)
    religion        = models.CharField(max_length=50, blank=True)

    # ── Professional ──────────────────────────────────────────────────────
    qualification     = models.CharField(max_length=20, choices=QUALIFICATION_CHOICES, blank=True)
    specialization    = models.CharField(max_length=150, blank=True)
    date_employed     = models.DateField(null=True, blank=True)
    employment_status = models.CharField(
        max_length=20, choices=EMPLOYMENT_STATUS_CHOICES,
        default="active", db_index=True,
    )

    # ── Teaching assignments (teachers only) ──────────────────────────────
    subjects_taught  = models.ManyToManyField(Subject, blank=True, related_name="teachers")
    assigned_classes = models.ManyToManyField(ClassArm, blank=True, related_name="teachers")

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Staff Profile"
        verbose_name_plural = "Staff Profiles"
        ordering            = ["school", "staff_id"]
        indexes             = [
            models.Index(fields=["school", "employment_status"]),
            models.Index(fields=["staff_id"]),
        ]

    def save(self, *args, **kwargs):
        if not self.staff_id:
            from .utils import generate_staff_id
            self.staff_id = generate_staff_id(self.school)
        super().save(*args, **kwargs)

    @property
    def full_name(self):
        return self.user.full_name

    @property
    def role(self):
        return self.user.role

    def __str__(self):
        return f"{self.staff_id} — {self.full_name} [{self.role}]"


# ── SubjectAssignment ──────────────────────────────────────────────────────

class SubjectAssignment(models.Model):
    """
    Assigns a specific teacher to teach a specific subject
    in a specific class arm, for a given academic term.

    This is the authoritative record for:
      - Which teacher marks scores for Subject X in ClassArm Y
      - Result sheet generation (teacher's name on report card)
      - CBT exam assignment routing

    Unique together: one teacher-subject-classarm per term.
    A subject can have different teachers per class arm.
    """

    school    = models.ForeignKey(
        "tenants.School",
        on_delete=models.CASCADE,
        related_name="subject_assignments",
    )
    teacher   = models.ForeignKey(
        StaffProfile,
        on_delete=models.CASCADE,
        related_name="subject_assignments",
        limit_choices_to={"user__role": "teacher"},
    )
    subject   = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    class_arm = models.ForeignKey(
        ClassArm,
        on_delete=models.CASCADE,
        related_name="subject_assignments",
    )
    session   = models.ForeignKey(
        "academics.AcademicSession",
        on_delete=models.CASCADE,
        related_name="subject_assignments",
    )
    term      = models.ForeignKey(
        "academics.Term",
        on_delete=models.CASCADE,
        related_name="subject_assignments",
    )

    class Meta:
        verbose_name        = "Subject Assignment"
        verbose_name_plural = "Subject Assignments"
        ordering            = ["class_arm", "subject"]
        constraints         = [
            models.UniqueConstraint(
                fields=["teacher", "subject", "class_arm", "term"],
                name="unique_teacher_subject_arm_term",
            ),
            # A subject can only be assigned to ONE teacher per class arm per term
            models.UniqueConstraint(
                fields=["subject", "class_arm", "term"],
                name="unique_subject_arm_term",
            ),
        ]
        indexes = [
            models.Index(fields=["school", "term"]),
            models.Index(fields=["teacher", "term"]),
            models.Index(fields=["class_arm", "term"]),
        ]

    def __str__(self):
        return (
            f"{self.teacher.full_name} → "
            f"{self.subject.code} / {self.class_arm.full_name} "
            f"({self.term})"
        )