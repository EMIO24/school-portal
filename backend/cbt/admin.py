from django.contrib import admin
from .models import Topic, Question


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
