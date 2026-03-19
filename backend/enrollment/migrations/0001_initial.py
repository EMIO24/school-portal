"""enrollment/migrations/0001_initial.py"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ClassLevel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(choices=[("JSS1","JSS 1"),("JSS2","JSS 2"),("JSS3","JSS 3"),("SS1","SS 1"),("SS2","SS 2"),("SS3","SS 3")], max_length=10)),
                ("order_index", models.PositiveSmallIntegerField(default=0)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="class_levels", to="tenants.school")),
            ],
            options={"verbose_name": "Class Level", "ordering": ["order_index", "name"]},
        ),
        migrations.AddConstraint(model_name="classlevel",
            constraint=models.UniqueConstraint(fields=["school","name"], name="unique_class_level_per_school")),
        migrations.CreateModel(
            name="ClassArm",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=10)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="class_arms", to="tenants.school")),
                ("class_level", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="arms", to="enrollment.classlevel")),
                ("class_teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="homeroom_classes", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "Class Arm", "ordering": ["class_level__order_index", "name"]},
        ),
        migrations.AddConstraint(model_name="classarm",
            constraint=models.UniqueConstraint(fields=["school","class_level","name"], name="unique_arm_per_level_per_school")),
        migrations.CreateModel(
            name="Subject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("code", models.CharField(max_length=10)),
                ("category", models.CharField(choices=[("core","Core"),("elective","Elective"),("vocational","Vocational")], default="core", max_length=15)),
                ("max_ca_score", models.PositiveSmallIntegerField(default=40)),
                ("max_exam_score", models.PositiveSmallIntegerField(default=60)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subjects", to="tenants.school")),
                ("class_levels", models.ManyToManyField(blank=True, related_name="subjects", to="enrollment.classlevel")),
            ],
            options={"verbose_name": "Subject", "ordering": ["name"]},
        ),
        migrations.AddConstraint(model_name="subject",
            constraint=models.UniqueConstraint(fields=["school","code"], name="unique_subject_code_per_school")),
        migrations.CreateModel(
            name="StudentProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("admission_number", models.CharField(blank=True, max_length=30, unique=True)),
                ("admission_date", models.DateField(auto_now_add=True)),
                ("status", models.CharField(choices=[("active","Active"),("graduated","Graduated"),("withdrawn","Withdrawn"),("suspended","Suspended")], db_index=True, default="active", max_length=15)),
                ("dob", models.DateField(blank=True, null=True)),
                ("gender", models.CharField(blank=True, choices=[("male","Male"),("female","Female")], max_length=10)),
                ("state_of_origin", models.CharField(blank=True, max_length=50)),
                ("religion", models.CharField(blank=True, max_length=50)),
                ("guardian_name", models.CharField(blank=True, max_length=150)),
                ("guardian_phone", models.CharField(blank=True, max_length=20)),
                ("guardian_email", models.EmailField(blank=True)),
                ("guardian_relationship", models.CharField(blank=True, max_length=20)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="student_profile", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="students", to="tenants.school")),
                ("current_class", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="students", to="enrollment.classarm")),
            ],
            options={"verbose_name": "Student Profile", "ordering": ["school","admission_number"]},
        ),
        migrations.AddIndex(model_name="studentprofile", index=models.Index(fields=["school","status"], name="enrollment_sp_school_status_idx")),
        migrations.AddIndex(model_name="studentprofile", index=models.Index(fields=["admission_number"], name="enrollment_sp_adm_num_idx")),
    ]