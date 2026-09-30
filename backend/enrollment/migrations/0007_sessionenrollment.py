from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


def backfill_current_session_enrollments(apps, schema_editor):
    StudentProfile = apps.get_model("enrollment", "StudentProfile")
    SessionEnrollment = apps.get_model("enrollment", "SessionEnrollment")
    AcademicSession = apps.get_model("academics", "AcademicSession")

    for session in AcademicSession.objects.filter(is_current=True).iterator():
        students = StudentProfile.objects.filter(
            school_id=session.school_id,
            status="active",
            current_class_id__isnull=False,
        ).iterator()
        for student in students:
            SessionEnrollment.objects.get_or_create(
                student_id=student.pk,
                session_id=session.pk,
                defaults={
                    "school_id": session.school_id,
                    "class_arm_id": student.current_class_id,
                    "status": "active",
                    "entry_reason": "migration",
                    "enrolled_on": max(student.admission_date, session.start_date),
                    "notes": "Backfilled from StudentProfile.current_class during Batch 19 migration.",
                },
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0001_initial"),
        ("enrollment", "0006_migrationstudentreference_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SessionEnrollment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("active", "Active"), ("completed", "Completed"), ("withdrawn", "Withdrawn"), ("transferred", "Transferred"), ("graduated", "Graduated")], db_index=True, default="active", max_length=15)),
                ("entry_reason", models.CharField(choices=[("admission", "Admission"), ("promotion", "Promotion"), ("repeat", "Repeat"), ("migration", "Migration"), ("manual", "Manual")], default="manual", max_length=15)),
                ("enrolled_on", models.DateField()),
                ("exited_on", models.DateField(blank=True, null=True)),
                ("notes", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("class_arm", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="session_enrollments", to="enrollment.classarm")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_session_enrollments", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="session_enrollments", to="tenants.school")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="student_enrollments", to="academics.academicsession")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="session_enrollments", to="enrollment.studentprofile")),
            ],
            options={
                "ordering": ["session__start_date", "class_arm__class_level__order_index", "student__admission_number"],
                "indexes": [
                    models.Index(fields=["school", "session", "status"], name="enrollment_s_school__71af38_idx"),
                    models.Index(fields=["school", "class_arm", "session"], name="enrollment_s_school__f2394d_idx"),
                    models.Index(fields=["student", "session"], name="enrollment_s_student_69bed0_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("student", "session"), name="unique_student_session_enrollment"),
                    models.CheckConstraint(condition=models.Q(("exited_on__isnull", True), ("exited_on__gte", models.F("enrolled_on")), _connector="OR"), name="session_enrollment_exit_not_before_entry"),
                ],
            },
        ),
        migrations.RunPython(backfill_current_session_enrollments, noop_reverse),
    ]
