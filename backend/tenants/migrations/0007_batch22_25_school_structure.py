from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0006_batch21_student_presence_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="school",
            name="uses_class_arms",
            field=models.BooleanField(default=True, help_text="If false, each class level uses one implicit default placement container."),
        ),
        migrations.CreateModel(
            name="Campus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("code", models.CharField(max_length=30)),
                ("address", models.TextField(blank=True)),
                ("phone", models.CharField(blank=True, max_length=30)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("is_primary", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("school", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="campuses", to="tenants.school")),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.AddConstraint(
            model_name="campus",
            constraint=models.UniqueConstraint(fields=("school", "code"), name="unique_campus_code_per_school"),
        ),
        migrations.AddConstraint(
            model_name="campus",
            constraint=models.UniqueConstraint(condition=models.Q(("is_primary", True)), fields=("school",), name="one_primary_campus_per_school"),
        ),
    ]
