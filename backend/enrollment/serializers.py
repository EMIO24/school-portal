"""
enrollment/serializers.py
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from accounts.serializers import UserProfileSerializer
from .models import ClassArm, ClassLevel, StudentProfile, Subject

User = get_user_model()


# ── ClassLevel ─────────────────────────────────────────────────────────────

class ClassLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ClassLevel
        fields = ["id", "name", "order_index"]
        read_only_fields = ["id"]


# ── ClassArm ───────────────────────────────────────────────────────────────

class ClassArmSerializer(serializers.ModelSerializer):
    full_name         = serializers.ReadOnlyField()
    class_level_name  = serializers.CharField(source="class_level.name", read_only=True)
    teacher_name      = serializers.CharField(
        source="class_teacher.full_name", read_only=True, default=None
    )
    student_count     = serializers.SerializerMethodField()

    class Meta:
        model  = ClassArm
        fields = [
            "id", "class_level", "class_level_name",
            "name", "full_name",
            "class_teacher", "teacher_name",
            "student_count",
        ]
        read_only_fields = ["id", "full_name", "class_level_name",
                            "teacher_name", "student_count"]

    def get_student_count(self, obj) -> int:
        return obj.students.filter(status="active").count()


# ── Subject ────────────────────────────────────────────────────────────────

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Subject
        fields = [
            "id", "name", "code", "class_levels",
            "category", "max_ca_score", "max_exam_score", "max_total",
        ]
        read_only_fields = ["id", "max_total"]

    def validate(self, attrs):
        ca   = attrs.get("max_ca_score",   getattr(self.instance, "max_ca_score",   40))
        exam = attrs.get("max_exam_score",  getattr(self.instance, "max_exam_score", 60))
        if ca + exam != 100:
            raise serializers.ValidationError(
                "max_ca_score + max_exam_score must equal 100."
            )
        return attrs


# ── StudentProfile ─────────────────────────────────────────────────────────

class StudentProfileSerializer(serializers.ModelSerializer):
    """Full serializer — used for create, retrieve, update."""

    # Nested read-only fields
    full_name          = serializers.ReadOnlyField()
    email              = serializers.EmailField(source="user.email", read_only=True)
    first_name         = serializers.CharField(source="user.first_name", read_only=True)
    last_name          = serializers.CharField(source="user.last_name", read_only=True)
    profile_photo      = serializers.URLField(source="user.profile_photo", read_only=True)
    current_class_name = serializers.CharField(
        source="current_class.full_name", read_only=True, default=None
    )

    # Write-only fields for creating the user account alongside the profile
    new_email      = serializers.EmailField(write_only=True, required=False)
    new_first_name = serializers.CharField(write_only=True, required=False, max_length=150)
    new_last_name  = serializers.CharField(write_only=True, required=False, max_length=150)

    class Meta:
        model  = StudentProfile
        fields = [
            # Identifiers
            "id", "admission_number", "admission_date", "status",
            # From user
            "email", "first_name", "last_name", "full_name", "profile_photo",
            # Write fields for user account creation
            "new_email", "new_first_name", "new_last_name",
            # Personal
            "dob", "gender", "state_of_origin", "religion",
            # Academic
            "current_class", "current_class_name",
            # Guardian
            "guardian_name", "guardian_phone", "guardian_email",
            "guardian_relationship",
        ]
        read_only_fields = [
            "id", "admission_number", "admission_date",
            "email", "first_name", "last_name", "full_name",
            "profile_photo", "current_class_name",
        ]

    @transaction.atomic
    def create(self, validated_data):
        """
        Create both the User account and the StudentProfile in one transaction.
        Password defaults to the admission number — user must change on first login.
        """
        school      = validated_data.pop("school")
        email       = validated_data.pop("new_email",      None)
        first_name  = validated_data.pop("new_first_name", "")
        last_name   = validated_data.pop("new_last_name",  "")

        if not email:
            raise serializers.ValidationError({"new_email": "Email is required."})

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError(
                {"new_email": f"A user with email '{email}' already exists."}
            )

        user = User.objects.create_user(
            email=email,
            password="changeme",          # overwritten after admission_number is set
            first_name=first_name,
            last_name=last_name,
            role="student",
            school=school,
            must_change_password=True,
        )

        profile = StudentProfile.objects.create(
            user=user,
            school=school,
            **validated_data,
        )

        # Set the default password to the admission number
        user.set_password(profile.admission_number)
        user.save(update_fields=["password"])

        return profile


class StudentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list view — avoids N+1 on large datasets."""

    full_name          = serializers.ReadOnlyField()
    email              = serializers.EmailField(source="user.email", read_only=True)
    profile_photo      = serializers.URLField(source="user.profile_photo", read_only=True)
    current_class_name = serializers.CharField(
        source="current_class.full_name", read_only=True, default=None
    )

    class Meta:
        model  = StudentProfile
        fields = [
            "id", "admission_number", "full_name", "email",
            "profile_photo", "gender", "status",
            "current_class", "current_class_name",
            "admission_date",
        ]