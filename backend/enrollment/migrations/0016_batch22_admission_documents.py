import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0015_batch22_23_admissions_records_welfare"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AdmissionDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(choices=[("birth_certificate", "Birth Certificate"), ("previous_result", "Previous Result"), ("passport_photo", "Passport Photo"), ("medical", "Medical Document"), ("other", "Other")], max_length=30)),
                ("title", models.CharField(max_length=180)),
                ("document_url", models.URLField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("application", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="documents", to="enrollment.admissionapplication")),
                ("uploaded_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admission_documents_uploaded", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["kind", "created_at", "id"]},
        ),
    ]
