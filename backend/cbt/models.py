"""
backend/cbt/models.py

Question bank models for the CBT engine.

Topic     — subject-scoped topic tag (e.g. "Algebra", "Cell Biology")
Question  — tagged MCQ / True-False / Fill-in-the-blank question
"""

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
