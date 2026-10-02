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


class CurriculumSource(models.Model):
    """Provenance for curriculum material recorded by one school."""

    class Kind(models.TextChoices):
        GOVERNMENT = 'government', 'Government / regulator'
        EXAM_BODY = 'exam_body', 'Examination body'
        SCHOOL = 'school', 'School-authored reference'
        OTHER = 'other', 'Other'

    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT, related_name='curriculum_sources')
    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    jurisdiction = models.CharField(max_length=120, blank=True)
    authority = models.CharField(max_length=180, blank=True)
    source_url = models.URLField(blank=True)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='created_curriculum_sources')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['school', 'name'], name='unique_curriculum_source_name_per_school'),
        ]
        indexes = [models.Index(fields=['school', 'kind'], name='curr_src_school_kind_idx')]


class CurriculumVersion(models.Model):
    """An immutable identity for one published/referenced edition of a curriculum source."""

    source = models.ForeignKey(CurriculumSource, on_delete=models.PROTECT, related_name='versions')
    label = models.CharField(max_length=100)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    reference = models.CharField(max_length=180, blank=True)
    notes = models.CharField(max_length=500, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='created_curriculum_versions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source', 'label'], name='unique_curriculum_version_label'),
        ]

    @property
    def school_id(self):
        return self.source.school_id


class CurriculumApplicability(models.Model):
    """Pins a school session/class/subject to the curriculum version applicable for that year."""

    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT, related_name='curriculum_applicability')
    session = models.ForeignKey('academics.AcademicSession', on_delete=models.PROTECT,
                                related_name='curriculum_applicability')
    class_level = models.ForeignKey('enrollment.ClassLevel', on_delete=models.PROTECT,
                                    related_name='curriculum_applicability')
    subject = models.ForeignKey('enrollment.Subject', on_delete=models.PROTECT,
                                related_name='curriculum_applicability')
    curriculum_version = models.ForeignKey(CurriculumVersion, on_delete=models.PROTECT,
                                           related_name='applicability')
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='recorded_curriculum_applicability')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'session', 'class_level', 'subject'],
                name='unique_curriculum_applicability_scope',
            ),
        ]
        indexes = [models.Index(fields=['school', 'session', 'class_level', 'subject'], name='curr_app_scope_idx')]

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.session_id and self.session.school_id != self.school_id:
            errors['session'] = 'Session must belong to this school.'
        if self.class_level_id and self.class_level.school_id != self.school_id:
            errors['class_level'] = 'Class level must belong to this school.'
        if self.subject_id and self.subject.school_id != self.school_id:
            errors['subject'] = 'Subject must belong to this school.'
        if self.curriculum_version_id and self.curriculum_version.school_id != self.school_id:
            errors['curriculum_version'] = 'Curriculum version must belong to this school.'
        if errors:
            raise ValidationError(errors)


class SchoolAcademicStandard(models.Model):
    """Reusable institutional teaching standard, distinct from a term's execution plan."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        REVIEWED = 'reviewed', 'Reviewed'
        APPROVED = 'approved', 'Approved'

    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT, related_name='academic_standards')
    curriculum_version = models.ForeignKey(CurriculumVersion, on_delete=models.PROTECT,
                                           related_name='school_standards')
    class_level = models.ForeignKey('enrollment.ClassLevel', on_delete=models.PROTECT,
                                    related_name='academic_standards')
    subject = models.ForeignKey('enrollment.Subject', on_delete=models.PROTECT,
                                related_name='academic_standards')
    title = models.CharField(max_length=180)
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    supersedes = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT,
                                   related_name='revisions')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='created_academic_standards')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='reviewed_academic_standards')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='approved_academic_standards')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'class_level', 'subject', 'revision'],
                name='unique_academic_standard_revision',
            ),
        ]
        indexes = [models.Index(fields=['school', 'class_level', 'subject', 'status'], name='acad_std_scope_idx')]

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.class_level_id and self.class_level.school_id != self.school_id:
            errors['class_level'] = 'Class level must belong to this school.'
        if self.subject_id and self.subject.school_id != self.school_id:
            errors['subject'] = 'Subject must belong to this school.'
        if self.curriculum_version_id and self.curriculum_version.school_id != self.school_id:
            errors['curriculum_version'] = 'Curriculum version must belong to this school.'
        if self.supersedes_id:
            if self.supersedes.school_id != self.school_id:
                errors['supersedes'] = 'Previous revision must belong to this school.'
            elif (self.supersedes.class_level_id != self.class_level_id or
                  self.supersedes.subject_id != self.subject_id):
                errors['supersedes'] = 'Previous revision must have the same class and subject scope.'
            elif self.supersedes.revision >= self.revision:
                errors['revision'] = 'Revision must be newer than the standard it supersedes.'
        if errors:
            raise ValidationError(errors)


class AcademicStandardTopic(models.Model):
    """Reusable topic expectation within an institutional academic standard."""

    class Requirement(models.TextChoices):
        REQUIRED = 'required', 'Required curriculum'
        ENRICHMENT = 'enrichment', 'School enrichment'

    standard = models.ForeignKey(SchoolAcademicStandard, on_delete=models.PROTECT, related_name='topics')
    term = models.CharField(max_length=10, choices=(('first', 'First Term'), ('second', 'Second Term'),
                                                    ('third', 'Third Term')))
    title = models.CharField(max_length=180)
    description = models.CharField(max_length=500, blank=True)
    position = models.PositiveSmallIntegerField()
    recommended_week = models.PositiveSmallIntegerField(null=True, blank=True)
    requirement = models.CharField(max_length=12, choices=Requirement.choices, default=Requirement.REQUIRED)
    source_reference = models.CharField(max_length=180, blank=True)

    class Meta:
        ordering = ['term', 'position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['standard', 'term', 'position'],
                                    name='unique_academic_standard_topic_position'),
        ]


class AcademicStandardObjective(models.Model):
    topic = models.ForeignKey(AcademicStandardTopic, on_delete=models.PROTECT, related_name='objectives')
    text = models.CharField(max_length=300)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ['position']
        constraints = [
            models.UniqueConstraint(fields=['topic', 'position'], name='unique_academic_standard_objective_position'),
            models.UniqueConstraint(fields=['topic', 'text'], name='unique_academic_standard_objective_text'),
        ]


class LessonPlan(models.Model):
    """Teacher plan for one class/subject/term; reviewable evidence, not proof of delivery."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        REVIEWED = 'reviewed', 'Reviewed'
        APPROVED = 'approved', 'Approved'

    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT, related_name='lesson_plans')
    term = models.ForeignKey('academics.Term', on_delete=models.PROTECT, related_name='lesson_plans')
    class_arm = models.ForeignKey('enrollment.ClassArm', on_delete=models.PROTECT, related_name='lesson_plans')
    subject = models.ForeignKey('enrollment.Subject', on_delete=models.PROTECT, related_name='lesson_plans')
    curriculum_topic = models.ForeignKey(CurriculumTopic, on_delete=models.PROTECT, related_name='lesson_plans')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='lesson_plans')
    title = models.CharField(max_length=180)
    objectives = models.TextField(blank=True)
    activities = models.TextField(blank=True)
    assessment = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=1)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='reviewed_lesson_plans')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='approved_lesson_plans')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['school', 'term', 'class_arm', 'subject', 'status'], name='lesson_plan_scope_idx')]
        constraints = [
            models.UniqueConstraint(fields=['school', 'term', 'class_arm', 'subject', 'curriculum_topic', 'revision'],
                                    name='unique_lesson_plan_revision'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.term_id and self.term.session.school_id != self.school_id:
            errors['term'] = 'Term must belong to this school.'
        if self.class_arm_id and self.class_arm.school_id != self.school_id:
            errors['class_arm'] = 'Class must belong to this school.'
        if self.subject_id and self.subject.school_id != self.school_id:
            errors['subject'] = 'Subject must belong to this school.'
        if self.curriculum_topic_id:
            plan = self.curriculum_topic.week.plan
            if plan.school_id != self.school_id or plan.term_id != self.term_id or plan.subject_id != self.subject_id:
                errors['curriculum_topic'] = 'Topic must belong to this school, term and subject plan.'
            elif plan.class_level_id != self.class_arm.class_level_id:
                errors['curriculum_topic'] = 'Topic class level must match the selected class.'
        if self.teacher_id and (self.teacher.school_id != self.school_id or self.teacher.role not in ('teacher', 'class_teacher')):
            errors['teacher'] = 'Choose a teacher in this school.'
        if errors:
            raise ValidationError(errors)


class AcademicResource(models.Model):
    """Versioned institutional teaching resource that may outlive its author."""

    class Kind(models.TextChoices):
        NOTE = 'note', 'Lesson note'
        HANDOUT = 'handout', 'Handout'
        SLIDE = 'slide', 'Slide / presentation'
        WORKSHEET = 'worksheet', 'Worksheet'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SUBMITTED = 'submitted', 'Submitted'
        REVIEWED = 'reviewed', 'Reviewed'
        APPROVED = 'approved', 'Approved'

    school = models.ForeignKey('tenants.School', on_delete=models.PROTECT, related_name='academic_resources')
    class_level = models.ForeignKey('enrollment.ClassLevel', on_delete=models.PROTECT, related_name='academic_resources')
    subject = models.ForeignKey('enrollment.Subject', on_delete=models.PROTECT, related_name='academic_resources')
    standard_topic = models.ForeignKey(AcademicStandardTopic, null=True, blank=True, on_delete=models.PROTECT,
                                       related_name='resources')
    title = models.CharField(max_length=180)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    content = models.TextField(blank=True)
    external_url = models.URLField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=1)
    supersedes = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='revisions')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='created_academic_resources')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='reviewed_academic_resources')
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='approved_academic_resources')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['school', 'class_level', 'subject', 'status'], name='acad_res_scope_idx')]
        constraints = [
            models.UniqueConstraint(fields=['school', 'class_level', 'subject', 'title', 'revision'],
                                    name='unique_academic_resource_revision'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        errors = {}
        if self.class_level_id and self.class_level.school_id != self.school_id:
            errors['class_level'] = 'Class level must belong to this school.'
        if self.subject_id and self.subject.school_id != self.school_id:
            errors['subject'] = 'Subject must belong to this school.'
        if self.standard_topic_id:
            standard = self.standard_topic.standard
            if standard.school_id != self.school_id or standard.class_level_id != self.class_level_id or standard.subject_id != self.subject_id:
                errors['standard_topic'] = 'Standard topic must match this school, class and subject.'
        if self.supersedes_id:
            if self.supersedes.school_id != self.school_id:
                errors['supersedes'] = 'Previous resource revision must belong to this school.'
            elif self.supersedes.revision >= self.revision:
                errors['revision'] = 'Revision must be newer than the resource it supersedes.'
        if errors:
            raise ValidationError(errors)
