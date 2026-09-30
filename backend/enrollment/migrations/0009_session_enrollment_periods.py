from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0008_rename_sessionenrollment_indexes"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="sessionenrollment",
            name="unique_student_session_enrollment",
        ),
        migrations.AddConstraint(
            model_name="sessionenrollment",
            constraint=models.UniqueConstraint(
                fields=("student", "session"),
                condition=models.Q(status="active"),
                name="one_active_student_session_enrollment",
            ),
        ),
        migrations.AddIndex(
            model_name="sessionenrollment",
            index=models.Index(
                fields=["student", "session", "enrolled_on"],
                name="enr_sess_student_period_idx",
            ),
        ),
        migrations.AlterField(
            model_name="sessionenrollment",
            name="entry_reason",
            field=models.CharField(
                choices=[
                    ("admission", "Admission"),
                    ("promotion", "Promotion"),
                    ("repeat", "Repeat"),
                    ("migration", "Migration"),
                    ("manual", "Manual"),
                    ("transfer", "Transfer"),
                ],
                default="manual",
                max_length=15,
            ),
        ),
    ]
