"""
accounts/models.py

CustomUser — single user model for all roles in the platform.
Role + school_id are embedded in JWT payload (see settings/base.py).

Roles:
  superadmin   — platform owner, no school FK
  school_admin — manages one school
  teacher      — belongs to one school
  student      — belongs to one school
  parent       — belongs to one school (linked to student(s))
"""

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models
from django.utils import timezone


class CustomUserManager(BaseUserManager):
    """
    Manager for CustomUser.
    Email is the unique identifier — no username field.
    """

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates a platform-level superadmin.
        Django admin access requires is_staff=True + is_superuser=True.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "superadmin")
        extra_fields.setdefault("must_change_password", False)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)

    # ── Tenant-scoped helpers ─────────────────────────────────────────────────

    def for_school(self, school):
        """Return all users belonging to a specific school."""
        return self.get_queryset().filter(school=school)


class CustomUser(AbstractBaseUser, PermissionsMixin):
    """
    Platform-wide user model.

    - Superadmins: school=None, is_staff=True
    - All other roles: school FK is required
    """

    ROLE_CHOICES = [
        ("superadmin",   "Super Admin"),
        ("school_admin", "School Admin"),
        ("teacher",      "Teacher"),
        ("student",      "Student"),
        ("parent",       "Parent"),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    email      = models.EmailField(unique=True, verbose_name="Email address")
    first_name = models.CharField(max_length=150)
    last_name  = models.CharField(max_length=150)

    # ── Tenant link ───────────────────────────────────────────────────────────
    # null=True allows superadmin to exist without a school
    school = models.ForeignKey(
        "tenants.School",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
        help_text="Null only for superadmin. All other roles must have a school.",
    )

    # ── Role ──────────────────────────────────────────────────────────────────
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="student",
        db_index=True,
    )

    # ── Profile ───────────────────────────────────────────────────────────────
    phone_number  = models.CharField(max_length=20, blank=True)
    profile_photo = models.URLField(blank=True, help_text="Cloudinary URL")

    # ── Status flags ──────────────────────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        help_text="Deactivated users cannot log in.",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Grants access to the Django /superadmin/ panel.",
    )
    must_change_password = models.BooleanField(
        default=True,
        help_text=(
            "Force password change on first login. "
            "Set to False after user changes their password."
        ),
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    date_joined = models.DateTimeField(default=timezone.now)

    # ── Auth config ───────────────────────────────────────────────────────────
    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = CustomUserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["school", "role"]),
            models.Index(fields=["email"]),
        ]

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_superadmin(self) -> bool:
        return self.role == "superadmin"

    @property
    def is_school_admin(self) -> bool:
        return self.role == "school_admin"

    @property
    def is_teacher(self) -> bool:
        return self.role == "teacher"

    @property
    def is_student(self) -> bool:
        return self.role == "student"

    @property
    def is_parent(self) -> bool:
        return self.role == "parent"

    # ── Validation ────────────────────────────────────────────────────────────

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.role != "superadmin" and self.school is None:
            raise ValidationError(
                {"school": "A school is required for all non-superadmin roles."}
            )

    def __str__(self):
        return f"{self.full_name} <{self.email}> [{self.role}]"