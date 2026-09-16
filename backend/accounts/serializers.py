"""
accounts/serializers.py

Serializers for authentication and user profile management.
"""

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from tenants.serializers import SchoolPublicSerializer

from .models import CustomUser


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    """
    Validates email + password for the current tenant.
    On success, returns JWT token pair + user metadata.
    """

    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        email    = attrs["email"].lower().strip()
        password = attrs["password"]
        request  = self.context["request"]
        tenant   = getattr(request, "tenant", None)

        # ── Authenticate ──────────────────────────────────────────────────────
        user = authenticate(request=request, email=email, password=password)

        if user is None:
            raise serializers.ValidationError(
                "Invalid email or password. Please try again.",
                code="authentication_failed",
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "Your account has been deactivated. Contact your school admin.",
                code="account_disabled",
            )

        # ── Tenant membership check ───────────────────────────────────────────
        # Superadmins can log in from any subdomain (or the apex domain).
        if user.role != "superadmin":
            if tenant is None:
                raise serializers.ValidationError(
                    "Please log in via your school's subdomain.",
                    code="no_tenant",
                )
            if user.school_id != tenant.pk:
                raise serializers.ValidationError(
                    "You are not registered with this school.",
                    code="wrong_tenant",
                )

        attrs["user"] = user
        return attrs

    def get_tokens(self, user, mfa_version=None) -> dict:
        """Generate JWT token pair with custom claims."""
        refresh = RefreshToken.for_user(user)
        if mfa_version is not None:
            refresh["mfa"] = True
            refresh["mfa_version"] = mfa_version

        # Extra claims embedded in the token payload
        refresh["role"]      = user.role
        refresh["school_id"] = user.school_id
        refresh["full_name"] = user.full_name
        refresh.access_token["role"]      = user.role
        refresh.access_token["school_id"] = user.school_id
        refresh.access_token["full_name"] = user.full_name

        return {
            "access":  str(refresh.access_token),
            "refresh": str(refresh),
        }


# ── User Profile ──────────────────────────────────────────────────────────────

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Safe read/write serializer for user profile data.
    Excludes password and sensitive Django internals.
    """

    platform_access = serializers.SerializerMethodField()

    def get_platform_access(self, obj):
        return getattr(getattr(obj, "platform_security", None), "access_level", "owner") if obj.role == "superadmin" else None

    full_name = serializers.ReadOnlyField()
    school    = SchoolPublicSerializer(read_only=True)
    student_id = serializers.IntegerField(source="student_profile.id", read_only=True, default=None)
    class_arm_id = serializers.IntegerField(source="student_profile.current_class_id", read_only=True, default=None)

    class Meta:
        model  = CustomUser
        fields = [
            "id",
            "student_id",
            "class_arm_id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "platform_access",
            "role",
            "school",
            "phone_number",
            "profile_photo",
            "is_active",
            "must_change_password",
            "date_joined",
        ]
        read_only_fields = [
            "id",
            "email",
            "role",
            "school",
            "is_active",
            "must_change_password",
            "date_joined",
            "full_name",
            "platform_access",
        ]


# ── Change Password ───────────────────────────────────────────────────────────

class ChangePasswordSerializer(serializers.Serializer):
    """
    Validates current password then sets a new one.
    Also clears the must_change_password flag.
    """

    current_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        min_length=8,
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        # Run Django's built-in password validators
        validate_password(attrs["new_password"], self.context["request"].user)
        return attrs

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return user
