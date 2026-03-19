"""enrollment/migrations/0002_staffprofile.py"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("enrollment", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="StaffProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("staff_id", models.CharField(blank=True, max_length=30, unique=True, help_text="Auto-generated: SLUG-STAFF-XXXX")),
                ("dob", models.DateField(blank=True, null=True)),
                ("gender", models.CharField(blank=True, choices=[("male","Male"),("female","Female")], max_length=10)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("address", models.TextField(blank=True)),
                ("state_of_origin", models.CharField(blank=True, max_length=50)),
                ("religion", models.CharField(blank=True, max_length=50)),
                ("qualification", models.CharField(blank=True, choices=[("ssce","SSCE / WAEC"),("nd","ND / NCE"),("hnd","HND"),("bsc","B.Sc / B.Ed / BA"),("pgd","PGD"),("msc","M.Sc / M.Ed / MA"),("phd","Ph.D"),("other","Other")], max_length=20)),
                ("specialization", models.CharField(blank=True, max_length=150)),
                ("date_employed", models.DateField(blank=True, null=True)),
                ("employment_status", models.CharField(choices=[("active","Active"),("on_leave","On Leave"),("suspended","Suspended"),("terminated","Terminated"),("resigned","Resigned")], db_index=True, default="active", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="staff_profile", to=settings.AUTH_USER_MODEL)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="staff", to="tenants.school")),
                ("subjects_taught", models.ManyToManyField(blank=True, related_name="teachers", to="enrollment.subject")),
                ("assigned_classes", models.ManyToManyField(blank=True, related_name="teachers", to="enrollment.classarm")),
            ],
            options={"verbose_name": "Staff Profile", "verbose_name_plural": "Staff Profiles", "ordering": ["school", "staff_id"]},
        ),
        migrations.AddIndex(model_name="staffprofile", index=models.Index(fields=["school","employment_status"], name="enrollment_sp_staff_status_idx")),
        migrations.AddIndex(model_name="staffprofile", index=models.Index(fields=["staff_id"], name="enrollment_sp_staff_id_idx")),
    ]