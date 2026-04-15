"""
backend/results/serializers.py

Serializers for ResultRemark and the slip-data JSON payload.

SlipDataSerializer assembles the complete data dict consumed by both
the WeasyPrint HTML template and the browser-side MyResult preview.
"""

from rest_framework import serializers
from .models import ResultRemark, ScratchCard


class ResultRemarkSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model  = ResultRemark
        fields = [
            'id', 'student', 'student_name', 'term', 'class_arm',
            'class_teacher_remark', 'principal_remark',
            'computed_position', 'total_score', 'average_score',
            'subjects_offered', 'updated_at',
        ]
        read_only_fields = [
            'id', 'student', 'student_name', 'term', 'class_arm',
            'computed_position', 'total_score', 'average_score',
            'subjects_offered', 'updated_at',
        ]

    def get_student_name(self, obj):
        u = obj.student
        return f"{u.last_name} {u.first_name}".strip() or u.email


class RemarkPatchSerializer(serializers.ModelSerializer):
    """Only the editable remark fields — used by PATCH remarks/{student_id}/"""
    class Meta:
        model  = ResultRemark
        fields = ['class_teacher_remark', 'principal_remark']


class ScratchCardSerializer(serializers.ModelSerializer):
    generated_by_name = serializers.SerializerMethodField()
    term_name         = serializers.SerializerMethodField()

    class Meta:
        model  = ScratchCard
        fields = [
            'id', 'serial_number', 'batch_name', 'term', 'term_name',
            'price', 'is_used', 'used_at', 'generated_by_name', 'created_at',
        ]

    def get_generated_by_name(self, obj):
        if obj.generated_by:
            return f"{obj.generated_by.last_name} {obj.generated_by.first_name}".strip()
        return ''

    def get_term_name(self, obj):
        return str(obj.term) if obj.term else ''


class BatchStatsSerializer(serializers.Serializer):
    batch_name  = serializers.CharField()
    total       = serializers.IntegerField()
    used        = serializers.IntegerField()
    unused      = serializers.IntegerField()
    created_at  = serializers.DateTimeField()