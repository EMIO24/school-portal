from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0013_batch22_25_class_structure"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="classarm",
            name="unique_arm_per_level_per_school",
        ),
        migrations.AddConstraint(
            model_name="classarm",
            constraint=models.UniqueConstraint(
                condition=models.Q(("campus__isnull", True)),
                fields=("school", "class_level", "name"),
                name="unique_arm_per_level_school_no_campus",
            ),
        ),
        migrations.AddConstraint(
            model_name="classarm",
            constraint=models.UniqueConstraint(
                condition=models.Q(("campus__isnull", False)),
                fields=("school", "campus", "class_level", "name"),
                name="unique_arm_per_level_campus",
            ),
        ),
    ]
