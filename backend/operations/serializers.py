from rest_framework import serializers

from .models import AdmissionApplication, AdmissionDocument, StudentRecordEntry, WelfareCase, WelfareCaseUpdate


class AdmissionDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdmissionDocument
        fields = ["id", "kind", "title", "file_url", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class AdmissionApplicationSerializer(serializers.ModelSerializer):
    documents = AdmissionDocumentSerializer(many=True, read_only=True)
    applying_class_level_name = serializers.CharField(source="applying_class_level.name", read_only=True)
    preferred_campus_name = serializers.CharField(source="preferred_campus.name", read_only=True, default=None)

    class Meta:
        model = AdmissionApplication
        fields = [
            "id", "application_number", "first_name", "last_name", "dob", "gender",
            "guardian_name", "guardian_phone", "guardian_email", "applying_class_level",
            "applying_class_level_name", "preferred_campus", "preferred_campus_name",
            "previous_school", "notes", "status", "admitted_student", "documents",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "application_number", "status", "admitted_student", "created_at", "updated_at"]


class StudentRecordEntrySerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.CharField(source="recorded_by.full_name", read_only=True, default="")

    class Meta:
        model = StudentRecordEntry
        fields = ["id", "student", "kind", "title", "details", "document_url", "effective_date", "supersedes", "recorded_by_name", "created_at"]
        read_only_fields = ["id", "student", "recorded_by_name", "created_at"]


class WelfareCaseUpdateSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default="")

    class Meta:
        model = WelfareCaseUpdate
        fields = ["id", "note", "status_after", "created_by_name", "created_at"]


class WelfareCaseSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.full_name", read_only=True)
    class_name = serializers.CharField(source="class_arm_snapshot.full_name", read_only=True, default="")
    updates = WelfareCaseUpdateSerializer(many=True, read_only=True)

    class Meta:
        model = WelfareCase
        fields = [
            "id", "student", "student_name", "category", "severity", "title", "details",
            "status", "class_arm_snapshot", "class_name", "assigned_to", "resolved_at",
            "opened_at", "updated_at", "updates",
        ]
        read_only_fields = ["id", "status", "class_arm_snapshot", "resolved_at", "opened_at", "updated_at", "updates"]
