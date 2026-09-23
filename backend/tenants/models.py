"""
tenants/models.py

Defines the School model — the root tenant for the entire multi-tenant platform.
Every other model in the system will have a FK back to this model.
"""

from django.db import models
from django.utils.text import slugify


class School(models.Model):
    """
    Top-level tenant model. One row = one school on the platform.
    Accessed via subdomain: <slug>.myplatform.com
    """

    SUBSCRIPTION_CHOICES = [
        ("free", "Free"),
        ("basic", "Basic"),
        ("premium", "Premium"),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    name = models.CharField(max_length=255, help_text="Full official school name")
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-safe identifier, auto-generated from name if blank",
    )
    subdomain = models.CharField(
        max_length=100,
        unique=True,
        help_text="Subdomain prefix (e.g. 'greenfield' → greenfield.myplatform.com)",
    )

    # ── Branding ──────────────────────────────────────────────────────────────
    logo = models.URLField(blank=True, help_text="Cloudinary URL for school logo")
    theme_config = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "JSON object with keys: primary_color, secondary_color, "
            "accent_color, font_family"
        ),
    )

    # ── Contact / Info ────────────────────────────────────────────────────────
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    motto = models.CharField(max_length=255, blank=True)
    registration_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Ministry / government registration number",
    )

    # ── Platform meta ─────────────────────────────────────────────────────────
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive schools are rejected by TenantMiddleware",
    )
    subscription_plan = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_CHOICES,
        default="free",
    )
    approval_status = models.CharField(max_length=12, default="approved", choices=[
        ("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")])
    subscription_ends_on = models.DateField(null=True, blank=True)
    platform_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "School"
        verbose_name_plural = "Schools"
        ordering = ["name"]

    # ── Helpers ───────────────────────────────────────────────────────────────
    def save(self, *args, **kwargs):
        """Auto-populate slug and subdomain from name if not provided."""
        if not self.slug:
            self.slug = slugify(self.name)
        if not self.subdomain:
            self.subdomain = self.slug
        super().save(*args, **kwargs)

    def get_theme(self) -> dict:
        """Return theme_config with sensible Nigerian-school defaults."""
        defaults = {
            "layout": "scholar",
            "primary_color": "#173B56",
            "secondary_color": "#256D85",
            "accent_color": "#D8A548",
            "font_family": "Roboto, sans-serif",
        }
        return {**defaults, **self.theme_config}

    def __str__(self):
        return f"{self.name} ({self.subdomain})"

class SchoolActivity(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="platform_activity")
    actor = models.ForeignKey("accounts.CustomUser", null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=400)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class PlatformSecurity(models.Model):
    user = models.OneToOneField("accounts.CustomUser", on_delete=models.CASCADE, related_name="platform_security")
    access_level = models.CharField(max_length=12, choices=[("owner", "Owner"), ("viewer", "Read only")], default="owner")
    encrypted_secret = models.TextField(blank=True)
    enabled = models.BooleanField(default=False)
    last_step = models.BigIntegerField(default=-1)
    recovery_hashes = models.JSONField(default=list)
    session_version = models.PositiveIntegerField(default=1)
    challenge_nonce = models.CharField(max_length=64, blank=True)
    failures = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)


class PlatformEvent(models.Model):
    actor = models.ForeignKey("accounts.CustomUser", null=True, on_delete=models.SET_NULL)
    actor_email = models.EmailField(blank=True)
    action = models.CharField(max_length=100)
    target = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class DemoRequest(models.Model):
    school_name = models.CharField(max_length=255)
    contact_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    student_population = models.PositiveIntegerField()
    location = models.CharField(max_length=255)
    message = models.TextField(max_length=2000, blank=True)
    status = models.CharField(max_length=20, default='new', choices=[('new', 'New'), ('contacted', 'Contacted')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
