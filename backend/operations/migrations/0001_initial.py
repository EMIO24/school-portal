from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("accounts", "0006_batch21_principal_class_teacher_roles"),
        ("enrollment", "0013_batch22_25_class_structure"),
        ("tenants", "0007_batch22_25_school_structure"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("application_number", models.CharField(max_length=40)),
                ("first_name", models.CharField(max_length=150)),
                ("last_name", models.CharField(max_length=150)),
                ("dob", models.DateField(blank=True, null=True)),
                ("gender", models.CharField(blank=True, max_length=10)),
                ("guardian_name", models.CharField(max_length=150)),
                ("guardian_phone", models.CharField(max_length=30)),
                ("guardian_email", models.EmailField(blank=True, max_length=254)),
                ("previous_school", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("submitted","Submitted"),("under_review","Under review"),("offered","Offered"),("admitted","Admitted"),("rejected","Rejected"),("withdrawn","Withdrawn")], db_index=True, default="submitted", max_length=20)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("admitted_student", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="admission_application", to="enrollment.studentprofile")),
                ("applying_class_level", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="enrollment.classlevel")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_admission_applications", to=settings.AUTH_USER_MODEL)),
                ("preferred_campus", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="admission_applications", to="tenants.campus")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_admission_applications", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="admission_applications", to="tenants.school")),
            ],
            options={"ordering":["-created_at","-id"]},
        ),
        migrations.AddConstraint(
            model_name="admissionapplication",
            constraint=models.UniqueConstraint(fields=("school","application_number"), name="unique_admission_application_number_per_school"),
        ),
        migrations.AddIndex(
            model_name="admissionapplication",
            index=models.Index(fields=["school","status"], name="admission_school_status_idx"),
        ),
        migrations.CreateModel(
            name="AdmissionDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("birth_certificate","Birth certificate"),("previous_result","Previous result"),("passport_photo","Passport photo"),("medical","Medical document"),("other","Other")], max_length=30)),
                ("title", models.CharField(max_length=180)),
                ("file_url", models.URLField()),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="operations.admissionapplication")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["kind","id"]},
        ),
        migrations.CreateModel(
            name="StudentRecordEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("identity","Identity"),("guardian","Guardian"),("enrollment","Enrollment"),("document","Document"),("note","Official note")], max_length=20)),
                ("title", models.CharField(max_length=180)),
                ("details", models.TextField(blank=True)),
                ("document_url", models.URLField(blank=True)),
                ("effective_date", models.DateField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="student_records_recorded", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="student_record_entries", to="tenants.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="official_record_entries", to="enrollment.studentprofile")),
                ("supersedes", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="corrections", to="operations.studentrecordentry")),
            ],
            options={"ordering":["-effective_date","-id"]},
        ),
        migrations.AddIndex(
            model_name="studentrecordentry",
            index=models.Index(fields=["school","student","kind"], name="student_record_scope_idx"),
        ),
        migrations.CreateModel(
            name="WelfareCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.CharField(choices=[("attendance","Attendance"),("behaviour","Behaviour"),("academic","Academic support"),("health","Health"),("safeguarding","Safeguarding"),("other","Other")], max_length=20)),
                ("severity", models.CharField(choices=[("low","Low"),("medium","Medium"),("high","High"),("critical","Critical")], default="low", max_length=10)),
                ("title", models.CharField(max_length=180)),
                ("details", models.TextField()),
                ("status", models.CharField(choices=[("open","Open"),("monitoring","Monitoring"),("resolved","Resolved")], db_index=True, default="open", max_length=12)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_welfare_cases", to=settings.AUTH_USER_MODEL)),
                ("class_arm_snapshot", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="welfare_cases", to="enrollment.classarm")),
                ("opened_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="opened_welfare_cases", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="welfare_cases", to="tenants.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="welfare_cases", to="enrollment.studentprofile")),
            ],
            options={"ordering":["-opened_at","-id"]},
        ),
        migrations.AddIndex(
            model_name="welfarecase",
            index=models.Index(fields=["school","status","severity"], name="welfare_school_status_idx"),
        ),
        migrations.AddIndex(
            model_name="welfarecase",
            index=models.Index(fields=["school","student"], name="welfare_student_idx"),
        ),
        migrations.CreateModel(
            name="WelfareCaseUpdate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("note", models.TextField()),
                ("status_after", models.CharField(choices=[("open","Open"),("monitoring","Monitoring"),("resolved","Resolved")], max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("case", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="updates", to="operations.welfarecase")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering":["created_at","id"]},
        ),
    ]
