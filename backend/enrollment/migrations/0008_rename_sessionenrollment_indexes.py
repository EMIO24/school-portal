from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("enrollment", "0007_sessionenrollment"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="sessionenrollment",
            old_name="enrollment_s_school__71af38_idx",
            new_name="enr_sess_school_status_idx",
        ),
        migrations.RenameIndex(
            model_name="sessionenrollment",
            old_name="enrollment_s_school__f2394d_idx",
            new_name="enr_sess_school_class_idx",
        ),
        migrations.RenameIndex(
            model_name="sessionenrollment",
            old_name="enrollment_s_student_69bed0_idx",
            new_name="enr_sess_student_sess_idx",
        ),
    ]
