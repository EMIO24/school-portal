"""
tenants/serializers.py

Serializers for the School (tenant) model.
"""

from rest_framework import serializers

from .models import School


class SchoolSerializer(serializers.ModelSerializer):
    """
    Full serializer for School — used by superadmin onboarding and school/me.

    Read-only computed fields:
      - theme  : merged theme_config with platform defaults
    """

    theme = serializers.SerializerMethodField(
        help_text="theme_config merged with platform defaults"
    )

    class Meta:
        model = School
        fields = [
            "id",
            "name",
            "slug",
            "subdomain",
            "logo",
            "theme_config",
            "theme",          # computed
            "address",
            "phone",
            "email",
            "motto",
            "registration_number",
            "is_active",
            "subscription_plan",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "theme"]

    def get_theme(self, obj: School) -> dict:
        return obj.get_theme()

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_theme_config(self, value: dict) -> dict:
        from .branding import validate_theme
        return validate_theme(value)

    def validate_subdomain(self, value: str) -> str:
        """Ensure subdomain is lowercase and alphanumeric-hyphen only."""
        import re
        value = value.lower().strip()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", value):
            raise serializers.ValidationError(
                "Subdomain may only contain lowercase letters, digits, and hyphens. "
                "It must not start or end with a hyphen."
            )
        return value


class SchoolPublicSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for public-facing school info
    (e.g., login page branding — no sensitive fields).
    """

    entitlements = serializers.SerializerMethodField()
    theme = serializers.SerializerMethodField()

    class Meta:
        model = School
        fields = ["name", "slug", "subdomain", "logo", "theme", "motto", "entitlements"]

    def get_entitlements(self, obj):
        from .plans import entitlements
        return entitlements(obj)

    def get_theme(self, obj: School) -> dict:
        return obj.get_theme()
