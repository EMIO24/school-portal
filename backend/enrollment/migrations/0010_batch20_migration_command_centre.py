from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_optional_student_email"),
        ("enrollment", "0009_session_enrollment_periods"),
    ]

    operations = [
        migrations.CreateModel(
            name="MigrationJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(db_index=True, max_length=40)),
                ("source_name", models.CharField(blank=True, default="", max_length=120)),
                ("original_filename", models.CharField(max_length=255)),
                ("file_fingerprint", models.CharField(max_length=64)),
                ("file_format", models.CharField(blank=True, default="", max_length=12)),
                ("status", models.CharField(choices=[("inspected", "Inspected"), ("validated", "Validated"), ("importing", "Importing"), ("completed", "Completed"), ("completed_with_errors", "Completed with errors"), ("failed", "Failed")], db_index=True, default="inspected", max_length=24)),
                ("mapping_snapshot", models.JSONField(blank=True, default=dict)),
                ("total_rows", models.PositiveIntegerField(default=0)),
                ("create_count", models.PositiveIntegerField(default=0)),
                ("reuse_count", models.PositiveIntegerField(default=0)),
                ("reject_count", models.PositiveIntegerField(default=0)),
                ("review_count", models.PositiveIntegerField(default=0)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="migration_jobs_created", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="migration_jobs", to="tenants.school")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.CreateModel(
            name="MigrationMappingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(db_index=True, max_length=40)),
                ("name", models.CharField(max_length=120)),
                ("source_system", models.CharField(blank=True, default="", max_length=120)),
                ("mappings", models.JSONField(default=dict)),
                ("last_used_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="migration_mapping_profiles_created", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="migration_mapping_profiles", to="tenants.school")),
            ],
            options={"ordering": ["domain", "name"]},
        ),
        migrations.CreateModel(
            name="MigrationConflict",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row_number", models.PositiveIntegerField()),
                ("domain", models.CharField(max_length=40)),
                ("source_identity", models.CharField(blank=True, default="", max_length=255)),
                ("conflict_type", models.CharField(max_length=80)),
                ("source_payload", models.JSONField(default=dict)),
                ("candidate_matches", models.JSONField(default=list)),
                ("status", models.CharField(choices=[("open", "Open"), ("resolved", "Resolved"), ("ignored", "Ignored")], db_index=True, default="open", max_length=12)),
                ("resolution", models.JSONField(blank=True, default=dict)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("job", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="conflicts", to="enrollment.migrationjob")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="migration_conflicts_resolved", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["job_id", "row_number", "id"]},
        ),
        migrations.AddConstraint(
            model_name="migrationjob",
            constraint=models.UniqueConstraint(fields=("school", "domain", "file_fingerprint"), name="unique_migration_file_per_school_domain"),
        ),
        migrations.AddConstraint(
            model_name="migrationmappingprofile",
            constraint=models.UniqueConstraint(fields=("school", "domain", "name"), name="unique_migration_mapping_profile_name"),
        ),
        migrations.AddConstraint(
            model_name="migrationconflict",
            constraint=models.UniqueConstraint(fields=("job", "row_number", "conflict_type"), name="unique_migration_conflict_per_row_type"),
        ),
    ]
