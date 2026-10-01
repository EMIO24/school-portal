# Generated for Batch 19E rollover safety foundation.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def normalize_current_sessions(apps, schema_editor):
    AcademicSession = apps.get_model("academics", "AcademicSession")
    School = apps.get_model("tenants", "School")
    for school_id in School.objects.values_list("pk", flat=True).iterator():
        current = list(
            AcademicSession.objects.filter(school_id=school_id, is_current=True)
            .order_by("-start_date", "-pk")
            .values_list("pk", flat=True)
        )
        if len(current) > 1:
            AcademicSession.objects.filter(pk__in=current[1:]).update(is_current=False)


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0002_alter_term_next_term_begins"),
        ("tenants", "0005_alter_school_subscription_plan"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AcademicRollover",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("preparing", "Preparing"), ("ready", "Ready"), ("completed", "Completed"), ("cancelled", "Cancelled")], db_index=True, default="preparing", max_length=12)),
                ("preview_snapshot", models.JSONField(blank=True, default=dict)),
                ("configuration_options", models.JSONField(blank=True, default=dict)),
                ("student_count", models.PositiveIntegerField(default=0)),
                ("promoted_count", models.PositiveIntegerField(default=0)),
                ("repeated_count", models.PositiveIntegerField(default=0)),
                ("graduated_count", models.PositiveIntegerField(default=0)),
                ("withdrawn_count", models.PositiveIntegerField(default=0)),
                ("idempotency_key", models.CharField(blank=True, max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("completed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="completed_academic_rollovers", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_academic_rollovers", to=settings.AUTH_USER_MODEL)),
                ("destination_session", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rollovers_to", to="academics.academicsession")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="academic_rollovers", to="tenants.school")),
                ("source_session", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="rollovers_from", to="academics.academicsession")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.RunPython(normalize_current_sessions, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="academicsession",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_current", True)),
                fields=("school",),
                name="one_current_academic_session_per_school",
            ),
        ),
        migrations.AddConstraint(
            model_name="academicrollover",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "completed")),
                fields=("school", "source_session", "destination_session"),
                name="one_completed_rollover_per_session_pair",
            ),
        ),
        migrations.AddConstraint(
            model_name="academicrollover",
            constraint=models.UniqueConstraint(
                condition=models.Q(("idempotency_key", ""), _negated=True),
                fields=("school", "idempotency_key"),
                name="unique_school_rollover_idempotency_key",
            ),
        ),
        migrations.AddConstraint(
            model_name="academicrollover",
            constraint=models.CheckConstraint(
                condition=models.Q(("source_session", models.F("destination_session")), _negated=True),
                name="rollover_sessions_must_differ",
            ),
        ),
    ]
