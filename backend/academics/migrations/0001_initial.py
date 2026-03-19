"""academics/migrations/0001_initial.py"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=20, help_text="e.g. '2024/2025'")),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("is_current", models.BooleanField(default=False, db_index=True)),
                (
                    "school",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to="tenants.school",
                    ),
                ),
            ],
            options={"verbose_name": "Academic Session", "verbose_name_plural": "Academic Sessions", "ordering": ["-start_date"]},
        ),
        migrations.AddConstraint(
            model_name="academicsession",
            constraint=models.UniqueConstraint(
                fields=["school", "name"], name="unique_session_name_per_school"
            ),
        ),
        migrations.CreateModel(
            name="Term",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(choices=[("first", "First Term"), ("second", "Second Term"), ("third", "Third Term")], max_length=10)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("is_current", models.BooleanField(default=False, db_index=True)),
                ("next_term_begins", models.DateField(blank=True, null=True, help_text="First day of next term")),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="terms",
                        to="academics.academicsession",
                    ),
                ),
            ],
            options={"verbose_name": "Term", "verbose_name_plural": "Terms", "ordering": ["session__start_date", "name"]},
        ),
        migrations.AddConstraint(
            model_name="term",
            constraint=models.UniqueConstraint(
                fields=["session", "name"], name="unique_term_per_session"
            ),
        ),
        migrations.CreateModel(
            name="Holiday",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("holiday_type", models.CharField(
                    choices=[("public", "Public Holiday"), ("school", "School Holiday"), ("exam_break", "Exam Break")],
                    default="public", max_length=20,
                )),
                (
                    "term",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="holidays",
                        to="academics.term",
                    ),
                ),
            ],
            options={"verbose_name": "Holiday", "verbose_name_plural": "Holidays", "ordering": ["start_date"]},
        ),
    ]