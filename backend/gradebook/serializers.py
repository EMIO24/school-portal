"""
backend/gradebook/serializers.py

Serializers for ScoreEntry, AffectiveDomain, PsychomotorDomain.

Key design:
  - ScoreEntryReadSerializer  — full denormalised row for the spreadsheet UI
  - ScoreEntryWriteSerializer — validates CA component caps, injects school/teacher
  - BulkScoreUpdateSerializer — wraps a list of write items for POST bulk-update/
  - Domain serializers        — straightforward ModelSerializer with rating bounds
"""

from decimal import Decimal
from rest_framework import serializers

from .models import (
    GradeScale, ScoreEntry,
    AffectiveDomain, PsychomotorDomain,
)

# ─────────────────────────────────────────────────────────────────────────────
# Grade Scale
# ─────────────────────────────────────────────────────────────────────────────

class GradeScaleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = GradeScale
        fields = ['id', 'min_score', 'max_score', 'grade', 'remark']


# ─────────────────────────────────────────────────────────────────────────────
# Score Entry — READ
# ─────────────────────────────────────────────────────────────────────────────

class ScoreEntryReadSerializer(serializers.ModelSerializer):
    student_name    = serializers.SerializerMethodField()
    student_admission = serializers.CharField(
        source='student.student_profile.admission_number', read_only=True, default=''
    )
    subject_name    = serializers.CharField(source='subject.name',    read_only=True)
    class_arm_name  = serializers.CharField(source='class_arm.name',  read_only=True)

    class Meta:
        model  = ScoreEntry
        fields = [
            'id',
            'student', 'student_name', 'student_admission',
            'subject', 'subject_name',
            'class_arm', 'class_arm_name',
            'term', 'session',
            'first_test', 'second_test', 'assignment', 'project', 'practical',
            'ca_total', 'exam_score', 'total_score',
            'grade', 'remark',
            'is_published',
            'updated_at',
        ]

    def get_student_name(self, obj):
        u = obj.student
        return f"{u.last_name} {u.first_name}".strip() or u.email


# ─────────────────────────────────────────────────────────────────────────────
# Score Entry — WRITE (single)
# ─────────────────────────────────────────────────────────────────────────────

# Maximum marks per CA component — matches Nigerian convention.
# Schools can override these via a settings JSONField if needed;
# for now we hard-code the standard split.
CA_MAXIMA = {
    'first_test':  10,
    'second_test': 10,
    'assignment':  10,
    'project':      5,
    'practical':    5,
}
MAX_CA_TOTAL = 40
MAX_EXAM     = 60


class ScoreEntryWriteSerializer(serializers.ModelSerializer):

    class Meta:
        model  = ScoreEntry
        fields = [
            'student', 'subject', 'class_arm', 'term', 'session',
            'first_test', 'second_test', 'assignment', 'project', 'practical',
            'exam_score',
        ]

    def _school(self):
        return self.context['request'].tenant

    def validate(self, attrs):
        errors = {}

        # Validate each CA component against its individual maximum
        for field, max_val in CA_MAXIMA.items():
            val = attrs.get(field, Decimal('0')) or Decimal('0')
            if val > max_val:
                errors[field] = f'Cannot exceed {max_val} marks.'
            if val < 0:
                errors[field] = 'Score cannot be negative.'

        # Validate CA total
        ca_sum = sum(
            attrs.get(f, Decimal('0')) or Decimal('0')
            for f in CA_MAXIMA
        )
        if ca_sum > MAX_CA_TOTAL:
            errors['ca_total'] = f'CA total ({ca_sum}) exceeds maximum of {MAX_CA_TOTAL}.'

        # Validate exam score
        exam = attrs.get('exam_score', Decimal('0')) or Decimal('0')
        if exam > MAX_EXAM:
            errors['exam_score'] = f'Exam score cannot exceed {MAX_EXAM}.'
        if exam < 0:
            errors['exam_score'] = 'Exam score cannot be negative.'

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        req = self.context['request']
        validated_data['school']  = self._school()
        validated_data['teacher'] = req.user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data['teacher'] = self.context['request'].user
        return super().update(instance, validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# Bulk score update
# ─────────────────────────────────────────────────────────────────────────────

class BulkScoreItemSerializer(serializers.Serializer):
    """One row in the bulk payload."""
    student_id   = serializers.IntegerField()
    first_test   = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False, default=Decimal('0'))
    second_test  = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False, default=Decimal('0'))
    assignment   = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False, default=Decimal('0'))
    project      = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False, default=Decimal('0'))
    practical    = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False, default=Decimal('0'))
    exam_score   = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False, default=Decimal('0'))


class BulkScoreUpdateSerializer(serializers.Serializer):
    class_arm  = serializers.IntegerField()
    subject    = serializers.IntegerField()
    term       = serializers.IntegerField()
    session    = serializers.IntegerField()
    scores     = BulkScoreItemSerializer(many=True)

    def validate_scores(self, value):
        if not value:
            raise serializers.ValidationError('scores list cannot be empty.')
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Affective Domain
# ─────────────────────────────────────────────────────────────────────────────

AFFECTIVE_FIELDS = [
    'punctuality', 'neatness', 'honesty', 'attentiveness',
    'relationship_with_others', 'leadership', 'creativity',
    'sport_games', 'handling_of_tools',
]

class AffectiveDomainSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model  = AffectiveDomain
        fields = ['id', 'student', 'student_name', 'class_arm', 'term'] + AFFECTIVE_FIELDS

    def get_student_name(self, obj):
        u = obj.student
        return f"{u.last_name} {u.first_name}".strip() or u.email

    def create(self, validated_data):
        validated_data['school'] = self.context['request'].tenant
        return super().create(validated_data)


# ─────────────────────────────────────────────────────────────────────────────
# Psychomotor Domain
# ─────────────────────────────────────────────────────────────────────────────

PSYCHOMOTOR_FIELDS = ['handwriting', 'drawing', 'verbal_fluency', 'musical_skills']

class PsychomotorDomainSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model  = PsychomotorDomain
        fields = ['id', 'student', 'student_name', 'class_arm', 'term'] + PSYCHOMOTOR_FIELDS

    def get_student_name(self, obj):
        u = obj.student
        return f"{u.last_name} {u.first_name}".strip() or u.email

    def create(self, validated_data):
        validated_data['school'] = self.context['request'].tenant
        return super().create(validated_data)