from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0012_batch21_class_teacher_relationships"),
        ("tenants", "0007_batch22_25_school_structure"),
    ]

    operations = [
        migrations.AddField(
            model_name="classarm",
            name="campus",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="class_arms_by_campus", to="tenants.campus"),
        ),
        migrations.AddField(
            model_name="classarm",
            name="is_default",
            field=models.BooleanField(default=False, help_text="System-managed implicit class container for schools that do not use arms."),
        ),
        migrations.AlterField(
            model_name="classarm",
            name="name",
            field=models.CharField(blank=True, help_text="Arm letter(s), e.g. 'A', 'B', 'Gold'. Blank for a no-arm school.", max_length=10),
        ),
        migrations.AddField(
            model_name="staffprofile",
            name="campus",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="staff_members", to="tenants.campus"),
        ),
    ]
