"""
tenants/migrations/0001_initial.py
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="School",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        help_text="Full official school name", max_length=255
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="URL-safe identifier, auto-generated from name if blank",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "subdomain",
                    models.CharField(
                        help_text="Subdomain prefix (e.g. 'greenfield' → greenfield.myplatform.com)",
                        max_length=100,
                        unique=True,
                    ),
                ),
                (
                    "logo",
                    models.URLField(
                        blank=True, help_text="Cloudinary URL for school logo"
                    ),
                ),
                (
                    "theme_config",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="JSON object with keys: primary_color, secondary_color, accent_color, font_family",
                    ),
                ),
                ("address", models.TextField(blank=True)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("motto", models.CharField(blank=True, max_length=255)),
                (
                    "registration_number",
                    models.CharField(
                        blank=True,
                        help_text="Ministry / government registration number",
                        max_length=100,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive schools are rejected by TenantMiddleware",
                    ),
                ),
                (
                    "subscription_plan",
                    models.CharField(
                        choices=[
                            ("free", "Free"),
                            ("basic", "Basic"),
                            ("premium", "Premium"),
                        ],
                        default="free",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "School",
                "verbose_name_plural": "Schools",
                "ordering": ["name"],
            },
        ),
    ]