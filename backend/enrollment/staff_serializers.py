"""
enrollment/staff_serializers.py

Serializers for StaffProfile — kept separate from student serializers
for clarity and independent import.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from accounts.school_access import TenantRelationsMixin

from .models import ClassArm, StaffProfile, Subject

User = get_user_model()


class StaffProfileSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    """Full serializer — create, retrieve, update."""

    # Read-only user fields
    user          = serializers.IntegerField(source="user_id", read_only=True)
    full_name     = serializers.ReadOnlyField()
    email         = serializers.EmailField(source="user.email",         read_only=True)
    first_name    = serializers.CharField(source="user.first_name",     read_only=True)
    last_name     = serializers.CharField(source="user.last_name",      read_only=True)
    profile_photo = serializers.URLField(source="user.profile_photo",   read_only=True)
    role          = serializers.CharField(source="user.role",           read_only=True)
    is_active     = serializers.BooleanField(source="user.is_active",   read_only=True)

    # Write-only fields for creating the user alongside the profile
    new_email      = serializers.EmailField(write_only=True, required=False)
    new_first_name = serializers.CharField(write_only=True, required=False, max_length=150)
    new_last_name  = serializers.CharField(write_only=True, required=False, max_length=150)
    new_role       = serializers.ChoiceField(
        choices=["school_admin", "teacher"],
        write_only=True, required=False, default="teacher",
    )

    # M2M display
    subjects_taught_detail  = serializers.SerializerMethodField()
    assigned_classes_detail = serializers.SerializerMethodField()

    class Meta:
        model  = StaffProfile
        fields = [
            "id", "user", "staff_id", "employment_status", "created_at",
            # User fields (read)
            "email", "first_name", "last_name", "full_name",
            "profile_photo", "role", "is_active",
            # Write fields for account creation
            "new_email", "new_first_name", "new_last_name", "new_role",
            # Personal
            "dob", "gender", "phone", "address",
            "state_of_origin", "religion",
            # Professional
            "qualification", "specialization", "date_employed",
            # Assignments (IDs for write, detail for read)
            "subjects_taught", "assigned_classes",
            "subjects_taught_detail", "assigned_classes_detail",
        ]
        read_only_fields = [
            "id", "user", "staff_id", "created_at",
            "email", "first_name", "last_name", "full_name",
            "profile_photo", "role", "is_active",
            "subjects_taught_detail", "assigned_classes_detail",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not (user and user.is_authenticated and user.school_id == instance.school_id
                and (user.role == "school_admin" or user.pk == instance.user_id)):
            for field in ("religion", "dob", "address", "phone", "state_of_origin"):
                data.pop(field, None)
        return data

    def get_subjects_taught_detail(self, obj):
        return [{"id": s.id, "name": s.name, "code": s.code}
                for s in obj.subjects_taught.all()]

    def get_assigned_classes_detail(self, obj):
        return [{"id": a.id, "full_name": a.full_name}
                for a in obj.assigned_classes.all()]

    @transaction.atomic
    def update(self, instance, validated_data):
        state = validated_data.get('employment_status')
        if state in ('suspended', 'terminated', 'resigned') and instance.user_id == self.context['request'].user.pk:
            raise serializers.ValidationError('Ask another administrator to deactivate your account.')
        from .account_editing import account_changes, edit_account
        edit_account(self.context['request'], instance.user, account_changes(validated_data))
        validated_data.pop('new_role', None)
        instance = super().update(instance, validated_data)
        if state in ('active', 'suspended', 'terminated', 'resigned'):
            instance.user.is_active = state == 'active'
            instance.user.save(update_fields=['is_active'])
            from tenants.models import PlatformEvent
            actor = self.context['request'].user
            PlatformEvent.objects.create(actor=actor, actor_email=actor.email, action='school.staff_access_changed',
                target=str(instance.pk), details={'school_id':instance.school_id, 'active':instance.user.is_active})
        return instance

    @transaction.atomic
    def create(self, validated_data):
        school      = validated_data.pop("school")
        email       = (validated_data.pop("new_email", None) or "").strip().lower()
        first_name  = validated_data.pop("new_first_name", "")
        last_name   = validated_data.pop("new_last_name",  "")
        role        = validated_data.pop("new_role",       "teacher")

        subjects_taught  = validated_data.pop("subjects_taught",  [])
        assigned_classes = validated_data.pop("assigned_classes", [])

        if not email:
            raise serializers.ValidationError({"new_email": "Email is required."})

        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                {"new_email": "This email cannot be used. Check the account details."}
            )

        user = User.objects.create_user(
            email=email,
            password="changeme",
            first_name=first_name,
            last_name=last_name,
            role=role,
            school=school,
            must_change_password=True,
            is_active=validated_data.get("employment_status", "active") not in ("suspended", "terminated", "resigned"),
        )

        profile = StaffProfile.objects.create(
            user=user, school=school, **validated_data
        )

        # Set password to staff_id
        user.set_password(profile.staff_id)
        user.save(update_fields=["password"])

        if subjects_taught:
            profile.subjects_taught.set(subjects_taught)
        if assigned_classes:
            profile.assigned_classes.set(assigned_classes)

        return profile


class StaffListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""

    full_name     = serializers.ReadOnlyField()
    email         = serializers.EmailField(source="user.email",       read_only=True)
    profile_photo = serializers.URLField(source="user.profile_photo", read_only=True)
    role          = serializers.CharField(source="user.role",         read_only=True)

    class Meta:
        model  = StaffProfile
        fields = [
            "id", "user", "staff_id", "full_name", "email",
            "profile_photo", "role",
            "specialization", "employment_status",
        ]
