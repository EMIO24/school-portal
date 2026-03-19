"""academics/admin.py"""

from django.contrib import admin
from .models import AcademicSession, Holiday, Term


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