from django.conf import settings
from django.db import models


class CurriculumPlan(models.Model):
    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT)
    term = models.ForeignKey('academics.Term', on_delete=models.PROTECT)
    class_level = models.ForeignKey('enrollment.ClassLevel', on_delete=models.PROTECT)
    subject = models.ForeignKey('enrollment.Subject', on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['school', 'term', 'class_level', 'subject'], name='unique_curriculum_scope')]


class CurriculumWeek(models.Model):
    plan = models.ForeignKey(CurriculumPlan, on_delete=models.PROTECT, related_name='weeks')
    number = models.PositiveSmallIntegerField()
    label = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['plan', 'number'], name='unique_curriculum_week')]


class CurriculumTopic(models.Model):
    week = models.ForeignKey(CurriculumWeek, on_delete=models.PROTECT, related_name='topics')
    title = models.CharField(max_length=180)
    description = models.CharField(max_length=500, blank=True)
    position = models.PositiveSmallIntegerField(default=1)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['week__number', 'position', 'id']
        constraints = [models.UniqueConstraint(fields=['week', 'position'], name='unique_topic_position')]


class LearningObjective(models.Model):
    topic = models.ForeignKey(CurriculumTopic, on_delete=models.PROTECT, related_name='objectives')
    text = models.CharField(max_length=300)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['position']
        constraints = [
            models.UniqueConstraint(fields=['topic', 'position'], name='unique_objective_position'),
            models.UniqueConstraint(fields=['topic', 'text'], name='unique_objective_text'),
        ]


class TopicCoverage(models.Model):
    class State(models.TextChoices):
        PARTIAL = 'partial', 'Partial'
        COVERED = 'covered', 'Covered'

    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT)
    lesson = models.ForeignKey('timetable.LessonRecord', on_delete=models.PROTECT, related_name='topic_coverage')
    topic = models.ForeignKey(CurriculumTopic, on_delete=models.PROTECT, related_name='coverage')
    state = models.CharField(max_length=8, choices=State.choices)
    note = models.CharField(max_length=300, blank=True)
    active = models.BooleanField(default=True)
    revision = models.PositiveIntegerField(default=1)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['lesson', 'topic'], name='unique_lesson_topic_coverage')]
        indexes = [models.Index(fields=['school', 'topic', 'active'])]
