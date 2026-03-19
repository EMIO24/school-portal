"""enrollment/admin.py"""

from django.contrib import admin
from .models import ClassArm, ClassLevel, StudentProfile, Subject, StaffProfile


@admin.register(ClassLevel)
class ClassLevelAdmin(admin.ModelAdmin):
    list_display  = ["name", "school", "order_index"]
    list_filter   = ["school"]
    ordering      = ["school", "order_index"]


@admin.register(ClassArm)
class ClassArmAdmin(admin.ModelAdmin):
    list_display  = ["full_name", "school", "class_teacher"]
    list_filter   = ["school", "class_level"]
    search_fields = ["name", "class_level__name"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display  = ["code", "name", "category", "max_ca_score", "max_exam_score", "school"]
    list_filter   = ["category", "school"]
    search_fields = ["name", "code"]
    filter_horizontal = ["class_levels"]


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display    = ["admission_number", "full_name", "current_class", "status", "school"]
    list_filter     = ["status", "gender", "school"]
    search_fields   = ["admission_number", "user__first_name", "user__last_name", "user__email"]
    readonly_fields = ["admission_number", "admission_date"]


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display    = ["staff_id", "full_name", "role", "specialization", "employment_status", "school"]
    list_filter     = ["employment_status", "qualification", "school", "user__role"]
    search_fields   = ["staff_id", "user__first_name", "user__last_name", "user__email", "specialization"]
    readonly_fields = ["staff_id", "created_at", "updated_at"]
    filter_horizontal = ["subjects_taught", "assigned_classes"]


from .models import SubjectAssignment

@admin.register(SubjectAssignment)
class SubjectAssignmentAdmin(admin.ModelAdmin):
    list_display  = ["teacher", "subject", "class_arm", "term", "school"]
    list_filter   = ["school", "term", "class_arm__class_level"]
    search_fields = ["teacher__user__last_name", "subject__name", "class_arm__name"]
    raw_id_fields = ["teacher", "subject", "class_arm", "session", "term"]