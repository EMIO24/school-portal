"""
backend/cbt/serializers.py
"""

from rest_framework import serializers
from .models import Topic, Question


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Topic
        fields = ['id', 'name', 'subject', 'class_level']


class QuestionSerializer(serializers.ModelSerializer):
    topic_name       = serializers.SerializerMethodField()
    subject_name     = serializers.SerializerMethodField()
    class_level_name = serializers.SerializerMethodField()

    class Meta:
        model  = Question
        fields = [
            'id', 'subject', 'subject_name', 'topic', 'topic_name',
            'class_level', 'class_level_name',
            'question_text', 'question_image', 'question_type',
            'difficulty', 'cognitive_level',
            'options', 'correct_answer', 'explanation',
            'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_topic_name(self, obj):
        return obj.topic.name if obj.topic else ''

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else ''

    def get_class_level_name(self, obj):
        return obj.class_level.name if obj.class_level else ''


class QuestionWriteSerializer(serializers.ModelSerializer):
    """Used for create/update — no computed read-only fields."""
    class Meta:
        model  = Question
        fields = [
            'subject', 'topic', 'class_level',
            'question_text', 'question_image', 'question_type',
            'difficulty', 'cognitive_level',
            'options', 'correct_answer', 'explanation', 'is_active',
        ]

    def validate_options(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('options must be a list.')
        for opt in value:
            if 'id' not in opt or 'text' not in opt:
                raise serializers.ValidationError("Each option must have 'id' and 'text'.")
        return value
