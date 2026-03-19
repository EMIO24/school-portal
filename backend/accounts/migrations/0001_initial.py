"""
accounts/migrations/0001_initial.py
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomUser",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                ("last_login", models.DateTimeField(blank=True, null=True, verbose_name="last login")),
                ("is_superuser", models.BooleanField(default=False)),
                ("email", models.EmailField(max_length=254, unique=True, verbose_name="Email address")),
                ("first_name", models.CharField(max_length=150)),
                ("last_name", models.CharField(max_length=150)),
                ("role", models.CharField(
                    choices=[
                        ("superadmin",   "Super Admin"),
                        ("school_admin", "School Admin"),
                        ("teacher",      "Teacher"),
                        ("student",      "Student"),
                        ("parent",       "Parent"),
                    ],
                    db_index=True,
                    default="student",
                    max_length=20,
                )),
                ("phone_number", models.CharField(blank=True, max_length=20)),
                ("profile_photo", models.URLField(blank=True, help_text="Cloudinary URL")),
                ("is_active", models.BooleanField(default=True)),
                ("is_staff", models.BooleanField(default=False)),
                ("must_change_password", models.BooleanField(default=True)),
                ("date_joined", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "school",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="users",
                        to="tenants.school",
                        help_text="Null only for superadmin.",
                    ),
                ),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        related_name="customuser_set",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        related_name="customuser_set",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "User",
                "verbose_name_plural": "Users",
                "ordering": ["last_name", "first_name"],
                "indexes": [
                    models.Index(fields=["school", "role"], name="accounts_cu_school_role_idx"),
                    models.Index(fields=["email"], name="accounts_cu_email_idx"),
                ],
            },
        ),
    ]