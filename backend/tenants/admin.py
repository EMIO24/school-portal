"""
tenants/admin.py

Register the School model in the Django admin site.
"""

from django.contrib import admin

from .models import School


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    """
    Admin configuration for the School (tenant) model.
    """

    list_display = [
        "name",
        "subdomain",
        "subscription_plan",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "subscription_plan"]
    search_fields = ["name", "subdomain", "slug", "email", "registration_number"]
    readonly_fields = ["created_at", "slug"]
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Identity",
            {
                "fields": ("name", "slug", "subdomain"),
            },
        ),
        (
            "Branding",
            {
                "fields": ("logo", "theme_config", "motto"),
            },
        ),
        (
            "Contact",
            {
                "fields": ("address", "phone", "email", "registration_number"),
            },
        ),
        (
            "Platform",
            {
                "fields": ("is_active", "subscription_plan", "created_at"),
            },
        ),
    )