"""
backend/cbt/serializers.py
"""

from rest_framework import serializers
from .models import Topic, Question, CBTExam, StudentExamSession, StudentAnswer


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


# ── CBT Exam serializers ──────────────────────────────────────────────────────

class CBTExamListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing exams (no question detail)."""
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    class_arms_display = serializers.SerializerMethodField()

    class Meta:
        model  = CBTExam
        fields = [
            'id', 'title', 'subject', 'subject_name',
            'class_arms_display',
            'start_datetime', 'end_datetime', 'duration_minutes',
            'status', 'show_score_immediately', 'allow_review',
            'instructions',
        ]

    def get_class_arms_display(self, obj):
        return [arm.full_name for arm in obj.class_arms.all()]


class CBTExamWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CBTExam
        fields = [
            'title', 'subject', 'class_arms', 'term', 'session',
            'start_datetime', 'end_datetime', 'duration_minutes', 'instructions',
            'selection_mode', 'manual_questions', 'random_config',
            'randomize_questions', 'randomize_options',
            'allow_review', 'show_score_immediately', 'status',
        ]


# ── Student-facing question (no correct_answer) ───────────────────────────────

class ExamQuestionSerializer(serializers.ModelSerializer):
    """
    Sent to the student during an active exam.
    correct_answer and explanation are deliberately excluded.
    Options are reordered per the session's option_map.
    """
    class Meta:
        model  = Question
        fields = [
            'id', 'question_text', 'question_image',
            'question_type', 'options',
        ]


# ── Session serializers ───────────────────────────────────────────────────────

class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model  = StudentAnswer
        fields = ['question', 'selected_option', 'time_spent_seconds']


class ExamSessionStatusSerializer(serializers.ModelSerializer):
    """Returned by the /status/ endpoint — includes saved answers."""
    saved_answers = StudentAnswerSerializer(source='answers', many=True, read_only=True)

    class Meta:
        model  = StudentExamSession
        fields = [
            'id', 'status', 'time_remaining_seconds',
            'tab_switch_count', 'score', 'saved_answers',
        ]
