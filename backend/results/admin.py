"""
backend/results/admin.py
"""
from django.contrib import admin
from .models import ResultRemark


@admin.register(ResultRemark)
class ResultRemarkAdmin(admin.ModelAdmin):
    list_display  = [
        'student', 'term', 'class_arm', 'computed_position',
        'average_score', 'subjects_offered', 'school'
    ]
    list_filter   = ['school', 'term', 'class_arm']
    search_fields = ['student__last_name', 'student__first_name']
    raw_id_fields = ['student', 'term', 'class_arm']
    readonly_fields = ['computed_position', 'total_score', 'average_score', 'subjects_offered']