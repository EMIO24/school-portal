from accounts.school_access import TenantRelationsMixin
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
            'is_published', 'review_state', 'component_scores', 'policy',
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
    component_scores = serializers.DictField(required=False)

    class Meta:
        model  = ScoreEntry
        fields = [
            'student', 'subject', 'class_arm', 'term', 'session',
            'first_test', 'second_test', 'assignment', 'project', 'practical',
            'exam_score', 'component_scores',
        ]

    def _school(self):
        return self.context['request'].tenant

    def validate(self, attrs):
        from accounts.school_access import require_assignment
        merged = {f: getattr(self.instance, f, None) for f in ('student','subject','class_arm','term','session')}
        merged.update(attrs)
        school = self._school()
        for key in ('student','subject','class_arm','session'):
            if not merged.get(key) or merged[key].school_id != school.pk:
                raise serializers.ValidationError({key: 'Select a record from this school.'})
        student, arm, term = merged['student'], merged['class_arm'], merged.get('term')
        if not term or term.session_id != merged['session'].pk or term.session.school_id != school.pk:
            raise serializers.ValidationError({'term':'Select a term in this session.'})
        if student.role != 'student' or getattr(getattr(student, 'student_profile', None), 'current_class_id', None) != arm.pk:
            raise serializers.ValidationError({'student':'Student must belong to the selected class.'})
        require_assignment(self.context['request'], arm.pk, term.pk, merged['subject'].pk)
        if self.instance and (self.instance.is_published or self.instance.review_state != 'draft'):
            raise serializers.ValidationError('Published grades are locked. Reopen through an audited correction first.')
        if self.instance and any(getattr(self.instance,k+'_id') != merged[k].pk for k in ('student','subject','class_arm','term','session')):
            raise serializers.ValidationError('An existing score cannot be moved to another academic context.')
        from .scoring import policy_for, checked_scores
        policy = self.instance.policy if self.instance and self.instance.policy_id else policy_for(school,term,create=True)
        values = attrs.get('component_scores')
        if values is None:
            values = {c['key']:attrs.get(c['key'],self.instance.component_scores.get(c['key']) if self.instance and self.instance.policy_id else getattr(self.instance,c['key'],None)) for c in policy.components}
        attrs['component_scores'] = checked_scores(policy,values)
        attrs['policy'] = policy
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
    component_scores = serializers.DictField(required=False)
    student_id   = serializers.IntegerField()
    first_test   = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False)
    second_test  = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False)
    assignment   = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False)
    project      = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False)
    practical    = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False)
    exam_score   = serializers.DecimalField(max_digits=5, decimal_places=2,
                                            required=False)


class BulkScoreUpdateSerializer(serializers.Serializer):
    class_arm  = serializers.IntegerField()
    subject    = serializers.IntegerField()
    term       = serializers.IntegerField()
    session    = serializers.IntegerField()
    scores     = BulkScoreItemSerializer(many=True)

    def validate_scores(self, value):
        if not value:
            raise serializers.ValidationError('scores list cannot be empty.')
        if len({row['student_id'] for row in value}) != len(value):
            raise serializers.ValidationError('Each student must appear once.')
        return value


# ─────────────────────────────────────────────────────────────────────────────
# Affective Domain
# ─────────────────────────────────────────────────────────────────────────────

AFFECTIVE_FIELDS = [
    'punctuality', 'neatness', 'honesty', 'attentiveness',
    'relationship_with_others', 'leadership', 'creativity',
    'sport_games', 'handling_of_tools',
]

class ResultDomainSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        from .lifecycle import require_unpublished
        school = self.context['request'].tenant
        require_unpublished(school, attrs.get('student', getattr(self.instance,'student',None)), attrs.get('term',getattr(self.instance,'term',None)))
        if self.instance:
            require_unpublished(school, self.instance.student, self.instance.term)
        return attrs


class AffectiveDomainSerializer(ResultDomainSerializer):
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

class PsychomotorDomainSerializer(ResultDomainSerializer):
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