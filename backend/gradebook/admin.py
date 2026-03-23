"""
backend/gradebook/admin.py
"""
from django.contrib import admin
from .models import GradeScale, ScoreEntry, AffectiveDomain, PsychomotorDomain


@admin.register(GradeScale)
class GradeScaleAdmin(admin.ModelAdmin):
    list_display = ['school', 'grade', 'min_score', 'max_score', 'remark']
    list_filter  = ['school', 'grade']
    ordering     = ['school', '-min_score']


@admin.register(ScoreEntry)
class ScoreEntryAdmin(admin.ModelAdmin):
    list_display  = ['student', 'subject', 'class_arm', 'term',
                     'ca_total', 'exam_score', 'total_score', 'grade', 'is_published']
    list_filter   = ['school', 'term', 'is_published', 'grade']
    search_fields = ['student__last_name', 'student__first_name', 'subject__name']
    raw_id_fields = ['student', 'subject', 'class_arm', 'term', 'session', 'teacher']
    readonly_fields = ['ca_total', 'total_score', 'grade', 'remark']


@admin.register(AffectiveDomain)
class AffectiveDomainAdmin(admin.ModelAdmin):
    list_display  = ['student', 'class_arm', 'term', 'school']
    list_filter   = ['school', 'term']
    raw_id_fields = ['student', 'class_arm', 'term']


@admin.register(PsychomotorDomain)
class PsychomotorDomainAdmin(admin.ModelAdmin):
    list_display  = ['student', 'class_arm', 'term', 'school']
    list_filter   = ['school', 'term']
    raw_id_fields = ['student', 'class_arm', 'term']