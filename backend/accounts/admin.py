"""
accounts/admin.py
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display  = ["email", "full_name", "role", "school", "is_active", "date_joined"]
    list_filter   = ["role", "is_active", "must_change_password", "school"]
    search_fields = ["email", "first_name", "last_name", "phone_number"]
    ordering      = ["email"]

    # Fields shown when EDITING an existing user
    fieldsets = (
        ("Credentials",  {"fields": ("email", "password")}),
        ("Personal",     {"fields": ("first_name", "last_name", "phone_number", "profile_photo")}),
        ("Role & Tenant",{"fields": ("role", "school")}),
        ("Status",       {"fields": ("is_active", "is_staff", "must_change_password")}),
        ("Permissions",  {"fields": ("is_superuser", "groups", "user_permissions")}),
        ("Dates",        {"fields": ("date_joined", "last_login")}),
    )

    # Fields shown when CREATING a new user
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "first_name", "last_name",
                "role", "school",
                "password1", "password2",
                "is_active", "must_change_password",
            ),
        }),
    )

    readonly_fields = ["date_joined", "last_login"]