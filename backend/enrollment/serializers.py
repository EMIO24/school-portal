"""
enrollment/serializers.py
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from accounts.serializers import UserProfileSerializer
from accounts.school_access import TenantRelationsMixin
from .models import ClassArm, ClassLevel, StudentProfile, Subject

User = get_user_model()


# ── ClassLevel ─────────────────────────────────────────────────────────────

class ClassLevelSerializer(serializers.ModelSerializer):
    def validate_name(self, value):
        qs = ClassLevel.objects.filter(school=self.context['request'].tenant, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('This class level already exists.')
        return value

    class Meta:
        model  = ClassLevel
        fields = ["id", "name", "order_index"]
        read_only_fields = ["id"]

    @transaction.atomic
    def create(self, validated_data):
        level = super().create(validated_data)
        school = self.context['request'].tenant
        if not school.uses_class_arms:
            from .class_structure import ensure_default_arm
            ensure_default_arm(school=school, class_level=level)
        return level


# ── ClassArm ───────────────────────────────────────────────────────────────

class ClassArmSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context['request'].tenant
        level = attrs.get('class_level', getattr(self.instance, 'class_level', None))
        name = attrs.get('name', getattr(self.instance, 'name', None))
        campus = attrs.get('campus', getattr(self.instance, 'campus', None))

        if not school.uses_class_arms and not getattr(self.instance, 'is_default', False):
            raise serializers.ValidationError({'name': 'This school does not use named class arms.'})
        if campus and campus.school_id != school.pk:
            raise serializers.ValidationError({'campus': 'Campus must belong to this school.'})
        if campus and not campus.is_active and (
                not self.instance or self.instance.campus_id != campus.pk):
            raise serializers.ValidationError({'campus': 'Choose an active campus for new placement.'})

        qs = ClassArm.objects.filter(school=school, class_level=level, name=name)
        qs = qs.filter(campus=campus) if campus else qs.filter(campus__isnull=True)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({'name':'This class already exists in this campus.'})
        return attrs

    full_name         = serializers.ReadOnlyField()
    class_level_name  = serializers.CharField(source="class_level.name", read_only=True)
    teacher_name      = serializers.CharField(
        source="class_teacher.full_name", read_only=True, default=None
    )
    campus_name       = serializers.CharField(source="campus.name", read_only=True, default=None)
    student_count     = serializers.SerializerMethodField()

    class Meta:
        model  = ClassArm
        fields = [
            "id", "class_level", "class_level_name",
            "name", "full_name", "is_default", "campus", "campus_name",
            "class_teacher", "teacher_name",
            "student_count",
        ]
        read_only_fields = ["id", "full_name", "class_level_name", "is_default",
                            "teacher_name", "campus_name", "student_count"]

    def get_student_count(self, obj) -> int:
        return obj.students.filter(status="active").count()

    def validate_class_teacher(self, value):
        if value and (value.role not in ('teacher', 'class_teacher') or not value.is_active):
            raise serializers.ValidationError('Select an active teacher.')
        return value


# ── Subject ────────────────────────────────────────────────────────────────

class SubjectSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    class Meta:
        model  = Subject
        fields = [
            "id", "name", "code", "class_levels",
            "category", "max_ca_score", "max_exam_score", "max_total",
        ]
        read_only_fields = ["id", "max_total"]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        ca   = attrs.get("max_ca_score",   getattr(self.instance, "max_ca_score",   40))
        exam = attrs.get("max_exam_score",  getattr(self.instance, "max_exam_score", 60))
        if ca + exam != 100:
            raise serializers.ValidationError(
                "max_ca_score + max_exam_score must equal 100."
            )
        return attrs


# ── StudentProfile ─────────────────────────────────────────────────────────

class StudentProfileSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    """Full serializer — used for create, retrieve, update."""

    # Nested read-only fields
    user               = serializers.IntegerField(source="user_id", read_only=True)
    full_name          = serializers.ReadOnlyField()
    email              = serializers.EmailField(source="user.email", read_only=True)
    first_name         = serializers.CharField(source="user.first_name", read_only=True)
    last_name          = serializers.CharField(source="user.last_name", read_only=True)
    profile_photo      = serializers.URLField(source="user.profile_photo", read_only=True)
    current_class_name = serializers.CharField(
        source="current_class.full_name", read_only=True, default=None
    )

    # Write-only fields for creating the user account alongside the profile
    new_email      = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    new_first_name = serializers.CharField(write_only=True, required=False, max_length=150)
    new_last_name  = serializers.CharField(write_only=True, required=False, max_length=150)

    class Meta:
        model  = StudentProfile
        fields = [
            # Identifiers
            "id", "user", "admission_number", "admission_date", "status",
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
            "user",
            "email", "first_name", "last_name", "full_name",
            "profile_photo", "current_class_name",
        ]

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if self.instance:
            if (
                "current_class" in attrs
                and attrs["current_class"] != self.instance.current_class
            ):
                raise serializers.ValidationError({
                    "current_class": (
                        "Use the controlled class-assignment workflow to change "
                        "a student's current class."
                    )
                })
            requested_status = self.initial_data.get("status")
            if (
                requested_status is not None
                and requested_status != self.instance.status
            ):
                raise serializers.ValidationError({
                    "status": (
                        "Use the controlled student lifecycle workflow to change "
                        "student status."
                    )
                })
        elif attrs.get("status", "active") != "active":
            raise serializers.ValidationError({
                "status": "New students must start with active status."
            })
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.role == "school_admin"
                and user.school_id == instance.school_id):
            data.pop("religion", None)
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        from .account_editing import account_changes, edit_account
        changes = account_changes(validated_data)
        edit_account(self.context['request'], instance.user, changes)
        return super().update(instance, validated_data)

    @transaction.atomic
    def create(self, validated_data):
        """
        Create both the User account and the StudentProfile in one transaction.
        Password defaults to the admission number — user must change on first login.
        """
        school      = validated_data.pop("school")
        email       = (validated_data.pop("new_email", None) or "").strip().lower()
        first_name  = validated_data.pop("new_first_name", "")
        last_name   = validated_data.pop("new_last_name",  "")

        if not email and (not first_name.strip() or not last_name.strip()):
            raise serializers.ValidationError("First and last name are required for student name login.")

        if email and User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                {"new_email": "This email cannot be used. Check the account details."}
            )

        user = User.objects.create_user(
            email=email,
            password="changeme",          # overwritten after admission_number is set
            first_name=first_name,
            last_name=last_name,
            role="student",
            school=school,
            must_change_password=True,
            is_active=validated_data.get("status", "active") == "active",
        )

        initial_class = validated_data.pop("current_class", None)
        profile = StudentProfile.objects.create(
            user=user,
            school=school,
            current_class=None,
            **validated_data,
        )

        if initial_class:
            from .session_enrollment import (
                EnrollmentPlacementError,
                ensure_current_enrollment,
            )
            request = self.context.get("request")
            actor = getattr(request, "user", None)
            if actor is None:
                actor = getattr(request, "_force_auth_user", None)
            if not getattr(actor, "is_authenticated", False):
                actor = None
            try:
                ensure_current_enrollment(
                    school=school,
                    student=profile,
                    class_arm=initial_class,
                    actor=actor,
                    entry_reason="admission",
                )
            except EnrollmentPlacementError as exc:
                raise serializers.ValidationError({
                    "current_class": str(exc)
                }) from exc

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
            "id", "user", "admission_number", "full_name", "email",
            "profile_photo", "gender", "status",
            "current_class", "current_class_name",
            "admission_date",
        ]
