from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_batch21_principal_class_teacher_roles"),
        ("enrollment", "0011_migrationconflict_created_at"),
    ]

    operations = [
        migrations.AlterField(
            model_name="classarm",
            name="class_teacher",
            field=models.ForeignKey(
                blank=True,
                limit_choices_to={"role__in": ["teacher", "class_teacher"]},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="homeroom_classes",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="subjectassignment",
            name="teacher",
            field=models.ForeignKey(
                limit_choices_to={"user__role__in": ["teacher", "class_teacher"]},
                on_delete=django.db.models.deletion.CASCADE,
                related_name="subject_assignments",
                to="enrollment.staffprofile",
            ),
        ),
    ]
