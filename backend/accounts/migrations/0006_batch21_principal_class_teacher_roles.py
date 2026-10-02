from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_optional_student_email"),
    ]

    operations = [
        migrations.AlterField(
            model_name="customuser",
            name="role",
            field=models.CharField(
                choices=[
                    ("superadmin", "Super Admin"),
                    ("school_admin", "School Admin"),
                    ("principal", "Principal"),
                    ("class_teacher", "Class Teacher"),
                    ("teacher", "Teacher"),
                    ("student", "Student"),
                    ("parent", "Parent"),
                ],
                db_index=True,
                default="student",
                max_length=20,
            ),
        ),
    ]
