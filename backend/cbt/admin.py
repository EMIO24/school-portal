from django.contrib import admin
from .models import Topic, Question, CBTExam, StudentExamSession, StudentAnswer


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display  = ['name', 'subject', 'class_level', 'school']
    list_filter   = ['school', 'subject', 'class_level']
    search_fields = ['name']


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'subject', 'topic', 'class_level', 'question_type', 'difficulty', 'is_active', 'school']
    list_filter   = ['school', 'subject', 'class_level', 'difficulty', 'question_type', 'cognitive_level', 'is_active']
    search_fields = ['question_text']
    raw_id_fields = ['subject', 'topic', 'class_level', 'created_by']


@admin.register(CBTExam)
class CBTExamAdmin(admin.ModelAdmin):
    list_display  = ['title', 'subject', 'status', 'start_datetime', 'end_datetime', 'duration_minutes', 'school']
    list_filter   = ['school', 'subject', 'status', 'selection_mode']
    search_fields = ['title']
    raw_id_fields = ['subject', 'term', 'session', 'created_by']
    filter_horizontal = ['class_arms', 'manual_questions']


@admin.register(StudentExamSession)
class StudentExamSessionAdmin(admin.ModelAdmin):
    list_display  = ['student', 'exam', 'status', 'score', 'started_at', 'submitted_at']
    list_filter   = ['status', 'exam__school']
    raw_id_fields = ['exam', 'student']


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display  = ['exam_session', 'question', 'selected_option', 'is_correct', 'time_spent_seconds']
    list_filter   = ['is_correct']
    raw_id_fields = ['exam_session', 'question']
