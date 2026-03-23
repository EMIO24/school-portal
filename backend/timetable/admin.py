"""
backend/timetable/admin.py
"""
from django.contrib import admin
from .models import Period, TimetableEntry


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display  = ['name', 'school', 'start_time', 'end_time', 'order_index', 'is_break']
    list_filter   = ['school', 'is_break']
    ordering      = ['school', 'order_index']


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display  = ['class_arm', 'day_of_week', 'period', 'subject', 'teacher', 'term']
    list_filter   = ['school', 'term', 'day_of_week']
    search_fields = ['class_arm__name', 'subject__name',
                     'teacher__first_name', 'teacher__last_name']
    raw_id_fields = ['teacher', 'subject', 'class_arm', 'term', 'period']