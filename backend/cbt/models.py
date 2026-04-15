"""
backend/cbt/models.py

Question bank and exam-engine models for the CBT engine.

Topic              — subject-scoped topic tag (e.g. "Algebra", "Cell Biology")
Question           — tagged MCQ / True-False / Fill-in-the-blank question
CBTExam            — exam configuration (scheduling, question selection, settings)
StudentExamSession — per-student shuffled snapshot of an exam
StudentAnswer      — per-question response recorded during an exam session
"""

import random

from django.conf import settings
from django.db import models


class Topic(models.Model):
    school      = models.ForeignKey('tenants.School',       on_delete=models.CASCADE, related_name='topics')
    subject     = models.ForeignKey('enrollment.Subject',   on_delete=models.CASCADE, related_name='topics')
    class_level = models.ForeignKey('enrollment.ClassLevel',on_delete=models.CASCADE, related_name='topics')
    name        = models.CharField(max_length=120)

    class Meta:
        unique_together = [('school', 'subject', 'class_level', 'name')]
        ordering        = ['subject__name', 'name']

    def __str__(self):
        return f"{self.name} ({self.subject.name})"


class Question(models.Model):

    QUESTION_TYPES = [
        ('mcq',        'Multiple Choice'),
        ('true_false', 'True / False'),
        ('fill_blank', 'Fill in the Blank'),
    ]

    DIFFICULTIES = [
        ('easy',   'Easy'),
        ('medium', 'Medium'),
        ('hard',   'Hard'),
    ]

    COGNITIVE_LEVELS = [
        ('knowledge',     'Knowledge'),
        ('comprehension', 'Comprehension'),
        ('application',   'Application'),
        ('analysis',      'Analysis'),
        ('synthesis',     'Synthesis'),
        ('evaluation',    'Evaluation'),
    ]

    school       = models.ForeignKey('tenants.School',       on_delete=models.CASCADE, related_name='questions')
    subject      = models.ForeignKey('enrollment.Subject',   on_delete=models.CASCADE, related_name='questions')
    topic        = models.ForeignKey(Topic, on_delete=models.SET_NULL, null=True, blank=True, related_name='questions')
    class_level  = models.ForeignKey('enrollment.ClassLevel',on_delete=models.CASCADE, related_name='questions')

    question_text  = models.TextField()
    question_image = models.URLField(blank=True, default='', help_text='Cloudinary URL (optional)')
    question_type  = models.CharField(max_length=20, choices=QUESTION_TYPES, default='mcq')
    difficulty     = models.CharField(max_length=10, choices=DIFFICULTIES,    default='medium')
    cognitive_level= models.CharField(max_length=20, choices=COGNITIVE_LEVELS,default='knowledge')

    # [{id: 'A', text: '...', image_url: null}, ...]
    options        = models.JSONField(default=list, blank=True)
    correct_answer = models.CharField(
        max_length=10, blank=True, default='',
        help_text="Option id for MCQ/true_false (e.g. 'A'), or answer text for fill_blank"
    )
    explanation    = models.TextField(blank=True, default='', help_text='Shown after submission')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_questions'
    )
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        preview = self.question_text[:60] + ('…' if len(self.question_text) > 60 else '')
        return f"[{self.get_difficulty_display()}] {preview}"


# ── CBT Exam ──────────────────────────────────────────────────────────────────

class CBTExam(models.Model):
    SELECTION_MODES = [
        ('manual',           'Manual — pick questions directly'),
        ('random_from_bank', 'Random from Question Bank'),
    ]
    STATUS_CHOICES = [
        ('draft',     'Draft'),
        ('published', 'Published'),
        ('ongoing',   'Ongoing'),
        ('completed', 'Completed'),
    ]

    school      = models.ForeignKey('tenants.School',          on_delete=models.CASCADE, related_name='cbt_exams')
    title       = models.CharField(max_length=200)
    subject     = models.ForeignKey('enrollment.Subject',      on_delete=models.CASCADE, related_name='cbt_exams')
    class_arms  = models.ManyToManyField('enrollment.ClassArm', blank=True, related_name='cbt_exams')
    term        = models.ForeignKey('academics.Term',          on_delete=models.CASCADE, related_name='cbt_exams')
    session     = models.ForeignKey('academics.AcademicSession', on_delete=models.CASCADE, related_name='cbt_exams')
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_exams'
    )

    start_datetime   = models.DateTimeField()
    end_datetime     = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    instructions     = models.TextField(blank=True, default='')

    selection_mode    = models.CharField(max_length=20, choices=SELECTION_MODES, default='random_from_bank')
    manual_questions  = models.ManyToManyField(Question, blank=True, related_name='manual_exams')
    # [{topic_id: N, count: N, difficulty: "medium"}, ...]
    random_config     = models.JSONField(default=list, blank=True)

    randomize_questions    = models.BooleanField(default=True)
    randomize_options      = models.BooleanField(default=True)
    allow_review           = models.BooleanField(default=True)
    show_score_immediately = models.BooleanField(default=True)

    status     = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_datetime']

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def resolve_questions(self):
        """
        Return the ordered list of Question objects for this exam.
        Manual mode: use manual_questions.
        Random mode: draw from the question bank per random_config rules.
        """
        if self.selection_mode == 'manual':
            qs = list(self.manual_questions.filter(is_active=True))
        else:
            qs = []
            for rule in self.random_config:
                topic_id   = rule.get('topic_id')
                count      = int(rule.get('count', 0))
                difficulty = rule.get('difficulty')
                pool = Question.objects.filter(school=self.school, is_active=True)
                if topic_id:
                    pool = pool.filter(topic_id=topic_id)
                if difficulty:
                    pool = pool.filter(difficulty=difficulty)
                pool = list(pool)
                random.shuffle(pool)
                qs.extend(pool[:count])

        if self.randomize_questions:
            random.shuffle(qs)
        return qs


# ── Student Exam Session ──────────────────────────────────────────────────────

class StudentExamSession(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('submitted',   'Submitted'),
        ('timed_out',   'Timed Out'),
    ]

    exam    = models.ForeignKey(CBTExam, on_delete=models.CASCADE, related_name='sessions')
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='exam_sessions', limit_choices_to={'role': 'student'}
    )

    # Ordered list of question IDs as the student will see them
    question_order = models.JSONField(default=list)
    # {str(question_id): {"A": "C", "B": "A", ...}} — maps original option id → shuffled position
    option_maps    = models.JSONField(default=dict)

    started_at             = models.DateTimeField(null=True, blank=True)
    submitted_at           = models.DateTimeField(null=True, blank=True)
    time_remaining_seconds = models.IntegerField(null=True, blank=True)

    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    score            = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    tab_switch_count = models.IntegerField(default=0)
    ip_address       = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        unique_together = [('exam', 'student')]

    def __str__(self):
        return f"{self.student} — {self.exam.title} ({self.get_status_display()})"


# ── Student Answer ────────────────────────────────────────────────────────────

class StudentAnswer(models.Model):
    exam_session    = models.ForeignKey(StudentExamSession, on_delete=models.CASCADE, related_name='answers')
    question        = models.ForeignKey(Question,           on_delete=models.CASCADE, related_name='student_answers')
    selected_option = models.CharField(max_length=10, blank=True, default='')
    is_correct      = models.BooleanField(null=True, blank=True)   # null until submitted
    time_spent_seconds = models.IntegerField(default=0)

    class Meta:
        unique_together = [('exam_session', 'question')]

    def __str__(self):
        return f"Answer({self.question_id}) → {self.selected_option or '—'}"
