"""
backend/attendance/admin.py
"""
from django.contrib import admin
from .models import AttendanceSession, AttendanceRecord


class AttendanceRecordInline(admin.TabularInline):
    model       = AttendanceRecord
    extra       = 0
    fields      = ['student', 'status', 'remark']
    raw_id_fields = ['student']


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display  = ['class_arm', 'date', 'mode', 'period', 'teacher', 'is_finalized', 'school']
    list_filter   = ['school', 'term', 'mode', 'is_finalized']
    search_fields = ['class_arm__name', 'teacher__first_name', 'teacher__last_name']
    raw_id_fields = ['teacher', 'class_arm', 'term', 'period']
    inlines       = [AttendanceRecordInline]
    date_hierarchy = 'date'


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display  = ['student', 'attendance_session', 'status', 'remark']
    list_filter   = ['status', 'attendance_session__school']
    search_fields = ['student__first_name', 'student__last_name']
    raw_id_fields = ['student', 'attendance_session']