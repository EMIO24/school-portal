from accounts.school_access import TenantRelationsMixin, require_assignment
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
            'source', 'term', 'curriculum_topic', 'marks',
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


class QuestionWriteSerializer(TenantRelationsMixin, serializers.ModelSerializer):
    """Used for create/update — no computed read-only fields."""
    class Meta:
        model  = Question
        fields = [
            'id',
            'subject', 'topic', 'class_level', 'term', 'curriculum_topic', 'marks',
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
            self.fields['term'].queryset = self.fields['term'].queryset.filter(session__school=getattr(request, 'tenant', None))
            self.fields['curriculum_topic'].queryset = self.fields['curriculum_topic'].queryset.filter(week__plan__school=getattr(request, 'tenant', None))

    def validate(self, attrs):
        attrs = super().validate(attrs)
        request = self.context['request']
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        level = attrs.get('class_level', getattr(self.instance, 'class_level', None))
        term = attrs.get('term', getattr(self.instance, 'term', None))
        curriculum_topic = attrs.get('curriculum_topic', getattr(self.instance, 'curriculum_topic', None))
        if attrs.get('marks', getattr(self.instance, 'marks', 1)) <= 0:
            raise serializers.ValidationError({'marks': 'Marks must be positive.'})
        kind = attrs.get('question_type', getattr(self.instance, 'question_type', 'mcq'))
        options = attrs.get('options', getattr(self.instance, 'options', []))
        answer = attrs.get('correct_answer', getattr(self.instance, 'correct_answer', ''))
        if kind in ('mcq', 'true_false'):
            ids = [option.get('id') for option in options]
            if len(ids) < 2 or len(ids) != len(set(ids)) or any(not str(option.get('text', '')).strip() for option in options):
                raise serializers.ValidationError({'options': 'Provide at least two distinct, non-empty choices.'})
            if answer not in ids:
                raise serializers.ValidationError({'correct_answer': 'Select one of the question choices.'})
        elif kind == 'fill_blank' and not str(answer).strip():
            raise serializers.ValidationError({'correct_answer': 'Provide the expected short answer.'})
        if request.tenant.subscription_plan == 'basic' and kind == 'theory':
            raise serializers.ValidationError({'question_type': 'Basic term CBT supports objective questions only.'})
        if curriculum_topic:
            plan = curriculum_topic.week.plan
            if plan.school_id != request.tenant.pk or plan.subject_id != subject.pk or plan.class_level_id != level.pk:
                raise serializers.ValidationError({'curriculum_topic': 'Choose a scheme topic for this school, subject and class.'})
            if term and plan.term_id != term.pk:
                raise serializers.ValidationError({'curriculum_topic': 'The scheme topic belongs to a different term.'})
            if not term:
                attrs['term'] = plan.term
                term = plan.term
        if request.tenant.subscription_plan == 'basic':
            from academics.models import Term
            current = Term.objects.filter(session__school=request.tenant, is_current=True).first()
            if not current or (term and term.pk != current.pk) or (self.instance and self.instance.term_id != current.pk):
                raise serializers.ValidationError({'term': 'Basic questions may be authored only for the current term.'})
            attrs['term'] = current
        if request.user.role == 'teacher':
            from enrollment.models import SubjectAssignment
            assignments = SubjectAssignment.objects.filter(school=request.tenant, teacher__user=request.user,
                teacher__employment_status='active', subject=subject, class_arm__class_level=level)
            if term:
                assignments = assignments.filter(term=term)
            if not assignments.exists():
                raise serializers.ValidationError({'subject': 'This subject and class are not assigned to you.'})
        return attrs

    def validate_options(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('options must be a list.')
        for opt in value:
            if not isinstance(opt, dict) or not isinstance(opt.get('id'), str) or not isinstance(opt.get('text'), str):
                raise serializers.ValidationError("Each option needs a text id and answer text.")
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
            'component_key',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        exam = self.instance
        value = lambda key, default=None: attrs.get(key, getattr(exam, key, default))
        request = self.context['request']
        school = request.tenant
        subject, term, session = value('subject'), value('term'), value('session')
        if not subject or subject.school_id != school.pk or not term or term.session.school_id != school.pk or not session or session.school_id != school.pk:
            raise serializers.ValidationError('Choose this school’s subject, term and session.')
        arms = attrs.get('class_arms', list(exam.class_arms.all()) if exam else [])
        if not arms or any(arm.school_id != school.pk for arm in arms):
            raise serializers.ValidationError({'class_arms': 'Choose classes in this school.'})
        if request.user.role == 'teacher':
            for arm in arms:
                require_assignment(request, arm.pk, term.pk, subject.pk)
        from .models import SubjectAssessmentMode
        if SubjectAssessmentMode.objects.filter(school=school, term=term, subject=subject,
                class_level_id__in=[arm.class_level_id for arm in arms], mode='paper').exists():
            raise serializers.ValidationError('This subject and class are configured for paper assessment.')
        if exam and exam.sessions.exists() and any(key in attrs for key in ('subject','term','session','class_arms','manual_questions','selection_mode','random_config','component_key')):
            raise serializers.ValidationError('An attempted exam cannot change its academic scope or questions.')
        if school.subscription_plan == 'basic':
            if not term.is_current or value('selection_mode') != 'manual':
                raise serializers.ValidationError('Basic CBT uses manually selected questions in the current term.')
            questions = attrs.get('manual_questions', list(exam.manual_questions.all()) if exam else [])
            if not questions or any(q.source != 'term' or q.term_id != term.pk for q in questions):
                raise serializers.ValidationError({'manual_questions': 'Choose current-term Basic questions only.'})
        else:
            questions = attrs.get('manual_questions', [])
            if questions and any(q.source != 'bank' for q in questions):
                raise serializers.ValidationError({'manual_questions': 'Choose reusable bank questions only.'})
        if any(q.school_id != school.pk or q.subject_id != subject.pk or q.class_level_id not in {arm.class_level_id for arm in arms} or q.question_type == 'theory' for q in questions):
            raise serializers.ValidationError({'manual_questions': 'Choose objective questions for this subject and class.'})
        component_key = value('component_key', '')
        if component_key:
            from gradebook.scoring import policy_for
            policy = policy_for(school, term)
            if not policy or component_key not in {c['key'] for c in policy.components}:
                raise serializers.ValidationError({'component_key': 'Choose a configured assessment component for this term.'})
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
