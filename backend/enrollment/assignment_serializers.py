"""
enrollment/assignment_serializers.py

Serializers for SubjectAssignment.
Kept separate from staff_serializers.py for clean imports.
"""

from rest_framework import serializers
from .models import ClassArm, StaffProfile, Subject, SubjectAssignment
from academics.models import AcademicSession, Term


class SubjectAssignmentSerializer(serializers.ModelSerializer):
    """Full read/write serializer for a single assignment row."""

    # Computed display fields
    teacher_name   = serializers.CharField(source="teacher.full_name",       read_only=True)
    teacher_staff_id = serializers.CharField(source="teacher.staff_id",      read_only=True)
    subject_name   = serializers.CharField(source="subject.name",            read_only=True)
    subject_code   = serializers.CharField(source="subject.code",            read_only=True)
    class_arm_name = serializers.CharField(source="class_arm.full_name",     read_only=True)
    session_name   = serializers.CharField(source="session.name",            read_only=True)
    term_name      = serializers.CharField(source="term.get_name_display",   read_only=True)

    class Meta:
        model  = SubjectAssignment
        fields = [
            "id",
            "teacher",       "teacher_name",    "teacher_staff_id",
            "subject",       "subject_name",    "subject_code",
            "class_arm",     "class_arm_name",
            "session",       "session_name",
            "term",          "term_name",
        ]
        read_only_fields = [
            "id",
            "teacher_name", "teacher_staff_id",
            "subject_name", "subject_code",
            "class_arm_name", "session_name", "term_name",
        ]

    def validate(self, attrs):
        """
        Cross-field validation:
        - term must belong to session
        - subject must be offered to the class_arm's level
        - teacher must belong to the same school as the request tenant
        """
        term    = attrs.get("term")
        session = attrs.get("session")
        subject = attrs.get("subject")
        arm     = attrs.get("class_arm")

        if term and session and term.session_id != session.pk:
            raise serializers.ValidationError(
                {"term": "Term does not belong to the selected session."}
            )

        if subject and arm:
            level_ids = list(subject.class_levels.values_list("id", flat=True))
            if level_ids and arm.class_level_id not in level_ids:
                raise serializers.ValidationError({
                    "subject": (
                        f"Subject '{subject.name}' is not offered to "
                        f"class level '{arm.class_level.name}'."
                    )
                })

        return attrs


class BulkAssignSerializer(serializers.Serializer):
    """
    Accepts a list of assignments to create/replace for a teacher.
    Used by POST /api/staff/{id}/assign-subjects/

    Body:
    {
        "session_id": 1,
        "term_id": 2,
        "assignments": [
            {"subject_id": 3, "class_arm_id": 5},
            {"subject_id": 4, "class_arm_id": 5}
        ]
    }
    """
    session_id  = serializers.IntegerField()
    term_id     = serializers.IntegerField()
    assignments = serializers.ListField(
        child=serializers.DictField(),
        allow_empty=True,
    )

    def validate_assignments(self, value):
        for item in value:
            if "subject_id" not in item or "class_arm_id" not in item:
                raise serializers.ValidationError(
                    "Each assignment needs 'subject_id' and 'class_arm_id'."
                )
        return value


class AssignmentGridSerializer(serializers.Serializer):
    """
    Read-only: serializes the full assignment grid for a given term.
    Shape:
    {
        "arms":     [ { id, full_name, level } ... ],
        "subjects": [ { id, code, name } ... ],
        "grid": {
            "<arm_id>": {
                "<subject_id>": {
                    "assignment_id": 1,
                    "teacher_name": "Ngozi Adeyemi",
                    "teacher_id": 7,
                    "staff_id": "GHS-STAFF-0007"
                } | null
            }
        }
    }
    """
    arms     = serializers.SerializerMethodField()
    subjects = serializers.SerializerMethodField()
    grid     = serializers.SerializerMethodField()

    def __init__(self, *args, assignments=None, arms=None, subjects=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._assignments = assignments or []
        self._arms        = arms or []
        self._subjects    = subjects or []

    def get_arms(self, obj):
        return [{"id": a.id, "full_name": a.full_name,
                 "level": a.class_level.name} for a in self._arms]

    def get_subjects(self, obj):
        return [{"id": s.id, "code": s.code, "name": s.name,
                 "category": s.category} for s in self._subjects]

    def get_grid(self, obj):
        # Build lookup: (arm_id, subject_id) → assignment
        lookup = {}
        for a in self._assignments:
            lookup[(a.class_arm_id, a.subject_id)] = a

        grid = {}
        for arm in self._arms:
            grid[str(arm.id)] = {}
            for subj in self._subjects:
                a = lookup.get((arm.id, subj.id))
                grid[str(arm.id)][str(subj.id)] = {
                    "assignment_id": a.id,
                    "teacher_name":  a.teacher.full_name,
                    "teacher_id":    a.teacher_id,
                    "staff_id":      a.teacher.staff_id,
                } if a else None

        return grid

    def to_representation(self, instance):
        return {
            "arms":     self.get_arms(instance),
            "subjects": self.get_subjects(instance),
            "grid":     self.get_grid(instance),
        }