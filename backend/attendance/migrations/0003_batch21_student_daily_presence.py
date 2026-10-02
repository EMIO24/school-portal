import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("attendance", "0002_initial"),
        ("enrollment", "0011_migrationconflict_created_at"),
        ("tenants", "0006_batch21_student_presence_settings"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="attendancesession",
            name="teacher",
            field=models.ForeignKey(
                limit_choices_to={"role__in": ["teacher", "class_teacher"]},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="attendance_sessions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="StudentDailyPresence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(db_index=True)),
                ("arrival_at", models.DateTimeField(blank=True, null=True)),
                ("departure_at", models.DateTimeField(blank=True, null=True)),
                ("correction_reason", models.CharField(blank=True, default="", max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("arrival_recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="student_arrivals_recorded", to=settings.AUTH_USER_MODEL)),
                ("departure_recorded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="student_departures_recorded", to=settings.AUTH_USER_MODEL)),
                ("class_arm", models.ForeignKey(blank=True, help_text="Class placement snapshot when this presence record was first created.", null=True, on_delete=django.db.models.deletion.PROTECT, related_name="student_presence_records", to="enrollment.classarm")),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_presence_records", to="tenants.school")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="daily_presence", to="enrollment.studentprofile")),
            ],
            options={"ordering": ["-date", "student__admission_number"]},
        ),
        migrations.AddConstraint(
            model_name="studentdailypresence",
            constraint=models.UniqueConstraint(fields=("school", "student", "date"), name="unique_student_daily_presence"),
        ),
        migrations.AddIndex(
            model_name="studentdailypresence",
            index=models.Index(fields=["school", "date"], name="presence_school_date_idx"),
        ),
    ]
