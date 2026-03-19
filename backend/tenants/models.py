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
            "primary_color": "#1a5276",
            "secondary_color": "#2e86c1",
            "accent_color": "#f39c12",
            "font_family": "Roboto, sans-serif",
        }
        return {**defaults, **self.theme_config}

    def __str__(self):
        return f"{self.name} ({self.subdomain})"