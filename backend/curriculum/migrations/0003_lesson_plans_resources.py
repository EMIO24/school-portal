from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0002_alter_term_next_term_begins'),
        ('curriculum', '0002_batch17_academic_standards'),
        ('enrollment', '0006_migrationstudentreference_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LessonPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180)),
                ('objectives', models.TextField(blank=True)),
                ('activities', models.TextField(blank=True)),
                ('assessment', models.TextField(blank=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('reviewed', 'Reviewed'), ('approved', 'Approved')], default='draft', max_length=12)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_lesson_plans', to=settings.AUTH_USER_MODEL)),
                ('class_arm', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lesson_plans', to='enrollment.classarm')),
                ('curriculum_topic', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lesson_plans', to='curriculum.curriculumtopic')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_lesson_plans', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lesson_plans', to='tenants.school')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lesson_plans', to='enrollment.subject')),
                ('teacher', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lesson_plans', to=settings.AUTH_USER_MODEL)),
                ('term', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='lesson_plans', to='academics.term')),
            ],
        ),
        migrations.CreateModel(
            name='AcademicResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180)),
                ('kind', models.CharField(choices=[('note', 'Lesson note'), ('handout', 'Handout'), ('slide', 'Slide / presentation'), ('worksheet', 'Worksheet'), ('other', 'Other')], max_length=12)),
                ('content', models.TextField(blank=True)),
                ('external_url', models.URLField(blank=True)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('reviewed', 'Reviewed'), ('approved', 'Approved')], default='draft', max_length=12)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_academic_resources', to=settings.AUTH_USER_MODEL)),
                ('class_level', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='academic_resources', to='enrollment.classlevel')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_academic_resources', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_academic_resources', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='academic_resources', to='tenants.school')),
                ('standard_topic', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='resources', to='curriculum.academicstandardtopic')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='academic_resources', to='enrollment.subject')),
                ('supersedes', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='revisions', to='curriculum.academicresource')),
            ],
        ),
        migrations.AddIndex(model_name='lessonplan', index=models.Index(fields=['school', 'term', 'class_arm', 'subject', 'status'], name='lesson_plan_scope_idx')),
        migrations.AddConstraint(model_name='lessonplan', constraint=models.UniqueConstraint(fields=('school', 'term', 'class_arm', 'subject', 'curriculum_topic', 'revision'), name='unique_lesson_plan_revision')),
        migrations.AddIndex(model_name='academicresource', index=models.Index(fields=['school', 'class_level', 'subject', 'status'], name='acad_res_scope_idx')),
        migrations.AddConstraint(model_name='academicresource', constraint=models.UniqueConstraint(fields=('school', 'class_level', 'subject', 'title', 'revision'), name='unique_academic_resource_revision')),
    ]
