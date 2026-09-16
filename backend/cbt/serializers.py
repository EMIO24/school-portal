from accounts.school_access import TenantRelationsMixin
"""
backend/cbt/serializers.py
"""

from rest_framework import serializers
from .models import Topic, Question, CBTExam, StudentExamSession, StudentAnswer


class TopicSerializer(TenantRelationsMixin, serializers.ModelSerializer):
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
            'id',
            'subject', 'topic', 'class_level',
            'question_text', 'question_image', 'question_type',
            'difficulty', 'cognitive_level',
            'options', 'correct_answer', 'explanation', 'is_active',
        ]
        read_only_fields = ['id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request is not None:
            for name in ('subject', 'class_level', 'topic'):
                self.fields[name].queryset = self.fields[name].queryset.filter(school=getattr(request, 'tenant', None))

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
            'id',
            'title', 'subject', 'class_arms', 'term', 'session',
            'start_datetime', 'end_datetime', 'duration_minutes', 'instructions',
            'selection_mode', 'manual_questions', 'random_config',
            'randomize_questions', 'randomize_options',
            'allow_review', 'show_score_immediately', 'status',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        exam = self.instance
        value = lambda key, default=None: attrs.get(key, getattr(exam, key, default))
        rules = value('random_config', [])
        if not isinstance(rules, list):
            raise serializers.ValidationError({'random_config': 'Rules must be a list.'})
        for rule in rules:
            if not isinstance(rule, dict) or type(rule.get('count')) is not int or not 1 <= rule['count'] <= 100:
                raise serializers.ValidationError({'random_config': 'Each rule needs a whole question count between 1 and 100.'})
            if rule.get('difficulty') not in (None, '', 'easy', 'medium', 'hard'):
                raise serializers.ValidationError({'random_config': 'Choose a valid difficulty.'})
            if rule.get('topic_id'):
                from .models import Topic
                request = self.context.get('request')
                school = getattr(request, 'tenant', None)
                if not str(rule['topic_id']).isdigit() or not Topic.objects.filter(pk=rule['topic_id'], school=school, subject=value('subject')).exists():
                    raise serializers.ValidationError({'random_config': 'Choose a topic belonging to the selected subject and school.'})
        if value('selection_mode') == 'random_from_bank' and not rules:
            raise serializers.ValidationError({'random_config': 'Add at least one question rule.'})
        if value('start_datetime') and value('end_datetime') and value('end_datetime') <= value('start_datetime'):
            raise serializers.ValidationError({'end_datetime': 'End time must be after start time.'})
        term, session = value('term'), value('session')
        if term and session and term.session_id != session.id:
            raise serializers.ValidationError({'term': 'Choose a term from the selected session.'})
        return attrs


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
