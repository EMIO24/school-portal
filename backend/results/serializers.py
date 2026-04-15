"""
backend/results/serializers.py

Serializers for ResultRemark and the slip-data JSON payload.

SlipDataSerializer assembles the complete data dict consumed by both
the WeasyPrint HTML template and the browser-side MyResult preview.
"""

from rest_framework import serializers
from .models import ResultRemark


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