"""
backend/timetable/serializers.py

Serializers for Period and TimetableEntry.

Validation strategy
-------------------
• Hard block  — teacher double-booked same day+period+term → 400 with message
• Soft warning — teacher >5 periods/day → stored as validated_data['_warning'],
                  surfaced in API response body as {"warning": "..."}, never a 400

The 'school' field is always injected from request.tenant; it is never
accepted from the client payload.
"""

from rest_framework import serializers
from .models import Period, TimetableEntry


# ─────────────────────────────────────────────────────────────────────────────
# Period
# ─────────────────────────────────────────────────────────────────────────────

class PeriodSerializer(serializers.ModelSerializer):

    class Meta:
        model  = Period
        fields = ['id', 'name', 'start_time', 'end_time', 'order_index', 'is_break']

    def validate(self, attrs):
        start = attrs.get('start_time')
        end   = attrs.get('end_time')
        if start and end and start >= end:
            raise serializers.ValidationError(
                {'end_time': 'End time must be after start time.'}
            )
        return attrs


# ─────────────────────────────────────────────────────────────────────────────
# TimetableEntry — READ (expanded, used by grid views)
# ─────────────────────────────────────────────────────────────────────────────

class TimetableEntryReadSerializer(serializers.ModelSerializer):
    """
    Flat, denormalised representation so the frontend grid can render
    each cell without additional fetches.
    """
    subject_name     = serializers.CharField(source='subject.name',           read_only=True)
    subject_color    = serializers.CharField(source='subject.category.color', read_only=True,
                                             default='')
    subject_category = serializers.CharField(source='subject.category.name',  read_only=True,
                                             default='')
    teacher_name     = serializers.SerializerMethodField()
    teacher_id       = serializers.IntegerField(source='teacher.id',          read_only=True)
    period_detail    = PeriodSerializer(source='period',                       read_only=True)
    class_arm_name   = serializers.CharField(source='class_arm.name',         read_only=True)

    class Meta:
        model  = TimetableEntry
        fields = [
            'id',
            'day_of_week',
            'period',           # FK id — used as dict key
            'period_detail',    # full period object for display
            'class_arm',
            'class_arm_name',
            'subject',
            'subject_name',
            'subject_color',
            'subject_category',
            'teacher',
            'teacher_id',
            'teacher_name',
            'term',
        ]

    def get_teacher_name(self, obj):
        if obj.teacher:
            return obj.teacher.get_full_name() or obj.teacher.username
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TimetableEntry — WRITE (POST / PATCH)
# ─────────────────────────────────────────────────────────────────────────────

class TimetableEntryWriteSerializer(serializers.ModelSerializer):

    class Meta:
        model  = TimetableEntry
        fields = ['id', 'term', 'class_arm', 'subject', 'teacher', 'day_of_week', 'period']

    # ── helpers ──────────────────────────────────────────────────────────────

    def _school(self):
        return self.context['request'].tenant

    # ── cross-field validation ────────────────────────────────────────────────

    def validate(self, attrs):
        school      = self._school()
        teacher     = attrs.get('teacher')
        day         = attrs.get('day_of_week')
        period      = attrs.get('period')
        term        = attrs.get('term')
        instance    = self.instance

        # ── 1. HARD BLOCK: teacher double-booking ────────────────────────────
        if teacher and day and period and term:
            conflict_qs = (
                TimetableEntry.objects
                .filter(school=school, teacher=teacher,
                        day_of_week=day, period=period, term=term)
            )
            if instance:
                conflict_qs = conflict_qs.exclude(pk=instance.pk)

            conflict = conflict_qs.select_related('class_arm').first()
            if conflict:
                day_label = dict(TimetableEntry.Day.choices)[day]
                raise serializers.ValidationError({
                    'teacher': (
                        f"{teacher.get_full_name()} is already assigned to "
                        f"{conflict.class_arm} during {day_label} "
                        f"{period.name} this term."
                    )
                })

        # ── 2. SOFT WARNING: overloaded day ──────────────────────────────────
        if teacher and day and term:
            load_qs = TimetableEntry.objects.filter(
                school=school, teacher=teacher, day_of_week=day, term=term
            )
            if instance:
                load_qs = load_qs.exclude(pk=instance.pk)

            count = load_qs.count()
            if count >= 5:
                day_label = dict(TimetableEntry.Day.choices)[day]
                attrs['_warning'] = (
                    f"{teacher.get_full_name()} will have {count + 1} periods "
                    f"on {day_label}. Consider redistributing their workload."
                )

        return attrs

    # ── save hooks ────────────────────────────────────────────────────────────

    def _pop_warning(self, validated_data):
        return validated_data.pop('_warning', None)

    def create(self, validated_data):
        self._pop_warning(validated_data)
        validated_data['school'] = self._school()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._pop_warning(validated_data)
        return super().update(instance, validated_data)