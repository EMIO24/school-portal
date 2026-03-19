"""enrollment/migrations/0003_subjectassignment.py"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0001_initial"),
        ("enrollment", "0002_staffprofile"),
        ("tenants",    "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SubjectAssignment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("school",    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subject_assignments", to="tenants.school")),
                ("teacher",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subject_assignments", to="enrollment.staffprofile")),
                ("subject",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assignments",          to="enrollment.subject")),
                ("class_arm", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subject_assignments",  to="enrollment.classarm")),
                ("session",   models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subject_assignments",  to="academics.academicsession")),
                ("term",      models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subject_assignments",  to="academics.term")),
            ],
            options={
                "verbose_name": "Subject Assignment",
                "verbose_name_plural": "Subject Assignments",
                "ordering": ["class_arm", "subject"],
            },
        ),
        migrations.AddConstraint(
            model_name="subjectassignment",
            constraint=models.UniqueConstraint(
                fields=["teacher", "subject", "class_arm", "term"],
                name="unique_teacher_subject_arm_term",
            ),
        ),
        migrations.AddConstraint(
            model_name="subjectassignment",
            constraint=models.UniqueConstraint(
                fields=["subject", "class_arm", "term"],
                name="unique_subject_arm_term",
            ),
        ),
        migrations.AddIndex(
            model_name="subjectassignment",
            index=models.Index(fields=["school", "term"], name="enrollment_sa_school_term_idx"),
        ),
        migrations.AddIndex(
            model_name="subjectassignment",
            index=models.Index(fields=["teacher", "term"], name="enrollment_sa_teacher_term_idx"),
        ),
        migrations.AddIndex(
            model_name="subjectassignment",
            index=models.Index(fields=["class_arm", "term"], name="enrollment_sa_arm_term_idx"),
        ),
    ]