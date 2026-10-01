"""academics/admin.py"""

from django.contrib import admin
from .models import AcademicRollover, AcademicSession, Holiday, Term


class TermInline(admin.TabularInline):
    model  = Term
    extra  = 0
    fields = ["name", "start_date", "end_date", "is_current", "next_term_begins"]


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display  = ["name", "school", "start_date", "end_date", "is_current"]
    list_filter   = ["school", "is_current"]
    search_fields = ["name", "school__name"]
    inlines       = [TermInline]


class HolidayInline(admin.TabularInline):
    model  = Holiday
    extra  = 0
    fields = ["name", "start_date", "end_date", "holiday_type"]


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display  = ["name", "session", "start_date", "end_date", "is_current"]
    list_filter   = ["is_current", "name", "session__school"]
    inlines       = [HolidayInline]


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display  = ["name", "term", "start_date", "end_date", "holiday_type"]
    list_filter   = ["holiday_type", "term__session__school"]

@admin.register(AcademicRollover)
class AcademicRolloverAdmin(admin.ModelAdmin):
    list_display = ["school", "source_session", "destination_session", "status", "created_at", "completed_at"]
    list_filter = ["status", "school"]
    search_fields = ["school__name", "source_session__name", "destination_session__name", "idempotency_key"]
    readonly_fields = ["preview_snapshot", "configuration_options", "created_at", "updated_at", "completed_at"]
