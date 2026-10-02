import django.db.models.deletion
import enrollment.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0014_batch25_campus_class_uniqueness"),
        ("tenants", "0007_batch22_25_school_structure"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("application_number", models.CharField(default=enrollment.models.generate_admission_application_number, editable=False, max_length=20, unique=True)),
                ("first_name", models.CharField(max_length=150)),
                ("last_name", models.CharField(max_length=150)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("dob", models.DateField(blank=True, null=True)),
                ("gender", models.CharField(blank=True, choices=[("male", "Male"), ("female", "Female")], max_length=10)),
                ("guardian_name", models.CharField(max_length=150)),
                ("guardian_phone", models.CharField(max_length=20)),
                ("guardian_email", models.EmailField(blank=True, max_length=254)),
                ("previous_school", models.CharField(blank=True, max_length=180)),
                ("notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("new", "New"), ("under_review", "Under Review"), ("offered", "Offered"), ("admitted", "Admitted"), ("rejected", "Rejected"), ("withdrawn", "Withdrawn")], db_index=True, default="new", max_length=20)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("admitted_student", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="source_admission_application", to="enrollment.studentprofile")),
                ("applying_class_level", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="enrollment.classlevel")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admission_applications_created", to=settings.AUTH_USER_MODEL)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admission_applications_decided", to=settings.AUTH_USER_MODEL)),
                ("preferred_campus", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="tenants.campus")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="tenants.school")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="admissionapplication",
            index=models.Index(fields=["school", "status"], name="admission_school_status_idx"),
        ),
        migrations.AddIndex(
            model_name="admissionapplication",
            index=models.Index(fields=["school", "applying_class_level"], name="admission_school_level_idx"),
        ),
        migrations.CreateModel(
            name="StudentRecordEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("identity", "Identity"), ("guardian", "Guardian"), ("enrollment", "Enrollment"), ("document", "Document"), ("note", "Institutional Note")], max_length=20)),
                ("title", models.CharField(max_length=180)),
                ("details", models.TextField(blank=True)),
                ("document_url", models.URLField(blank=True)),
                ("effective_date", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="student_record_entries_created", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="student_record_entries", to="tenants.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="official_record_entries", to="enrollment.studentprofile")),
                ("supersedes", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="corrections", to="enrollment.studentrecordentry")),
            ],
            options={"ordering": ["-effective_date", "-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="studentrecordentry",
            index=models.Index(fields=["school", "student", "effective_date"], name="student_record_history_idx"),
        ),
        migrations.CreateModel(
            name="WelfareCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("attendance", "Attendance"), ("behaviour", "Behaviour"), ("academic", "Academic"), ("health", "Health"), ("safeguarding", "Safeguarding"), ("other", "Other")], max_length=20)),
                ("severity", models.CharField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")], default="low", max_length=10)),
                ("title", models.CharField(max_length=180)),
                ("details", models.TextField()),
                ("status", models.CharField(choices=[("open", "Open"), ("monitoring", "Monitoring"), ("resolved", "Resolved")], db_index=True, default="open", max_length=12)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("class_arm_snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="welfare_cases", to="enrollment.classarm")),
                ("reported_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="welfare_cases_reported", to=settings.AUTH_USER_MODEL)),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="welfare_cases_resolved", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="welfare_cases", to="tenants.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="welfare_cases", to="enrollment.studentprofile")),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
        migrations.AddIndex(
            model_name="welfarecase",
            index=models.Index(fields=["school", "status", "severity"], name="welfare_school_status_idx"),
        ),
        migrations.AddIndex(
            model_name="welfarecase",
            index=models.Index(fields=["school", "student"], name="welfare_school_student_idx"),
        ),
        migrations.CreateModel(
            name="WelfareUpdate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.TextField()),
                ("status_after", models.CharField(choices=[("open", "Open"), ("monitoring", "Monitoring"), ("resolved", "Resolved")], max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="welfare_updates_created", to=settings.AUTH_USER_MODEL)),
                ("welfare_case", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="updates", to="enrollment.welfarecase")),
            ],
            options={"ordering": ["created_at", "id"]},
        ),
    ]
