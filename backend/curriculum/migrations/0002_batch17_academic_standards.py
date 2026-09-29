from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0002_alter_term_next_term_begins'),
        ('curriculum', '0001_initial'),
        ('enrollment', '0006_migrationstudentreference_and_more'),
        ('tenants', '0005_alter_school_subscription_plan'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CurriculumSource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=180)),
                ('kind', models.CharField(choices=[('government', 'Government / regulator'), ('exam_body', 'Examination body'), ('school', 'School-authored reference'), ('other', 'Other')], max_length=20)),
                ('jurisdiction', models.CharField(blank=True, max_length=120)),
                ('authority', models.CharField(blank=True, max_length=180)),
                ('source_url', models.URLField(blank=True)),
                ('notes', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_curriculum_sources', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='curriculum_sources', to='tenants.school')),
            ],
        ),
        migrations.CreateModel(
            name='CurriculumVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=100)),
                ('effective_from', models.DateField(blank=True, null=True)),
                ('effective_to', models.DateField(blank=True, null=True)),
                ('reference', models.CharField(blank=True, max_length=180)),
                ('notes', models.CharField(blank=True, max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_curriculum_versions', to=settings.AUTH_USER_MODEL)),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='versions', to='curriculum.curriculumsource')),
            ],
        ),
        migrations.CreateModel(
            name='SchoolAcademicStandard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=180)),
                ('revision', models.PositiveIntegerField(default=1)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('submitted', 'Submitted'), ('reviewed', 'Reviewed'), ('approved', 'Approved')], default='draft', max_length=12)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('approved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='approved_academic_standards', to=settings.AUTH_USER_MODEL)),
                ('class_level', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='academic_standards', to='enrollment.classlevel')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_academic_standards', to=settings.AUTH_USER_MODEL)),
                ('curriculum_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='school_standards', to='curriculum.curriculumversion')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_academic_standards', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='academic_standards', to='tenants.school')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='academic_standards', to='enrollment.subject')),
                ('supersedes', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='revisions', to='curriculum.schoolacademicstandard')),
            ],
        ),
        migrations.CreateModel(
            name='CurriculumApplicability',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('class_level', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='curriculum_applicability', to='enrollment.classlevel')),
                ('curriculum_version', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='applicability', to='curriculum.curriculumversion')),
                ('recorded_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='recorded_curriculum_applicability', to=settings.AUTH_USER_MODEL)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='curriculum_applicability', to='tenants.school')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='curriculum_applicability', to='academics.academicsession')),
                ('subject', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='curriculum_applicability', to='enrollment.subject')),
            ],
        ),
        migrations.CreateModel(
            name='AcademicStandardTopic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('term', models.CharField(choices=[('first', 'First Term'), ('second', 'Second Term'), ('third', 'Third Term')], max_length=10)),
                ('title', models.CharField(max_length=180)),
                ('description', models.CharField(blank=True, max_length=500)),
                ('position', models.PositiveSmallIntegerField()),
                ('recommended_week', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('requirement', models.CharField(choices=[('required', 'Required curriculum'), ('enrichment', 'School enrichment')], default='required', max_length=12)),
                ('source_reference', models.CharField(blank=True, max_length=180)),
                ('standard', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='topics', to='curriculum.schoolacademicstandard')),
            ],
            options={'ordering': ['term', 'position', 'id']},
        ),
        migrations.CreateModel(
            name='AcademicStandardObjective',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.CharField(max_length=300)),
                ('position', models.PositiveSmallIntegerField()),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='objectives', to='curriculum.academicstandardtopic')),
            ],
            options={'ordering': ['position']},
        ),
        migrations.AddConstraint(model_name='curriculumsource', constraint=models.UniqueConstraint(fields=('school', 'name'), name='unique_curriculum_source_name_per_school')),
        migrations.AddIndex(model_name='curriculumsource', index=models.Index(fields=['school', 'kind'], name='curriculum_c_school__ad1c0d_idx')),
        migrations.AddConstraint(model_name='curriculumversion', constraint=models.UniqueConstraint(fields=('source', 'label'), name='unique_curriculum_version_label')),
        migrations.AddConstraint(model_name='curriculumapplicability', constraint=models.UniqueConstraint(fields=('school', 'session', 'class_level', 'subject'), name='unique_curriculum_applicability_scope')),
        migrations.AddIndex(model_name='curriculumapplicability', index=models.Index(fields=['school', 'session', 'class_level', 'subject'], name='curriculum_c_school__65dcb4_idx')),
        migrations.AddConstraint(model_name='schoolacademicstandard', constraint=models.UniqueConstraint(fields=('school', 'class_level', 'subject', 'revision'), name='unique_academic_standard_revision')),
        migrations.AddIndex(model_name='schoolacademicstandard', index=models.Index(fields=['school', 'class_level', 'subject', 'status'], name='curriculum_s_school__e2f410_idx')),
        migrations.AddConstraint(model_name='academicstandardtopic', constraint=models.UniqueConstraint(fields=('standard', 'term', 'position'), name='unique_academic_standard_topic_position')),
        migrations.AddConstraint(model_name='academicstandardobjective', constraint=models.UniqueConstraint(fields=('topic', 'position'), name='unique_academic_standard_objective_position')),
        migrations.AddConstraint(model_name='academicstandardobjective', constraint=models.UniqueConstraint(fields=('topic', 'text'), name='unique_academic_standard_objective_text')),
    ]
