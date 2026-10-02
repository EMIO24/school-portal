from decimal import Decimal

from rest_framework import serializers

from accounts.school_access import require_assignment
from gradebook.scoring import policy_for
from .models import SubjectAssessmentMode, ExamPaper, OnlineAssignment, Question


def validate_scope(request, term, subject, level, arm=None):
    school = request.tenant
    if term.session.school_id != school.pk or subject.school_id != school.pk or level.school_id != school.pk:
        raise serializers.ValidationError('Select academic records from this school.')
    if arm and (arm.school_id != school.pk or arm.class_level_id != level.pk):
        raise serializers.ValidationError({'class_arm': 'Choose a class in this school and level.'})
    if request.user.role in ('teacher', 'class_teacher'):
        if arm:
            require_assignment(request, arm.pk, term.pk, subject.pk)
        else:
            from enrollment.models import SubjectAssignment
            if not SubjectAssignment.objects.filter(school=school, teacher__user=request.user,
                    teacher__employment_status='active', term=term, subject=subject,
                    class_arm__class_level=level).exists():
                raise serializers.ValidationError('This subject and class are not assigned to you.')


class ModeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubjectAssessmentMode
        fields = ['id', 'term', 'class_level', 'subject', 'mode']

    def validate(self, attrs):
        request = self.context['request']
        current = self.instance
        term = attrs.get('term', getattr(current, 'term', None))
        subject = attrs.get('subject', getattr(current, 'subject', None))
        level = attrs.get('class_level', getattr(current, 'class_level', None))
        validate_scope(request, term, subject, level)
        if current and any(key in attrs for key in ('term', 'subject', 'class_level')):
            raise serializers.ValidationError('An existing assessment mode cannot change academic scope.')
        if attrs.get('mode') == 'paper':
            from .models import CBTExam
            if CBTExam.objects.filter(school=request.tenant, term=term, subject=subject,
                    class_arms__class_level=level, status__in=['published', 'ongoing', 'completed']).exists():
                raise serializers.ValidationError('This subject and class already have a published CBT for this term.')
        if attrs.get('mode') == 'cbt' and ExamPaper.objects.filter(school=request.tenant, term=term,
                subject=subject, class_level=level, status__in=['submitted', 'approved']).exists():
            raise serializers.ValidationError('This subject and class already have a submitted paper for this term.')
        return attrs


class PaperSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamPaper
        fields = ['id', 'term', 'class_level', 'subject', 'title', 'instructions',
                  'duration_minutes', 'blueprint', 'question_snapshot', 'status', 'approved_at']
        read_only_fields = ['id', 'question_snapshot', 'status', 'approved_at']

    def validate(self, attrs):
        request = self.context['request']
        paper = self.instance
        term = attrs.get('term', getattr(paper, 'term', None))
        subject = attrs.get('subject', getattr(paper, 'subject', None))
        level = attrs.get('class_level', getattr(paper, 'class_level', None))
        validate_scope(request, term, subject, level)
        if paper and paper.status != 'draft':
            raise serializers.ValidationError('Submitted or approved papers are locked.')
        if paper and paper.question_snapshot and any(key in attrs for key in ('term', 'subject', 'class_level', 'blueprint')):
            raise serializers.ValidationError('A generated paper cannot change its academic scope or blueprint.')
        if not SubjectAssessmentMode.objects.filter(school=request.tenant, term=term, subject=subject,
                class_level=level, mode='paper').exists():
            raise serializers.ValidationError('Set this subject and class to paper assessment first.')
        blueprint = attrs.get('blueprint', paper.blueprint if paper else [])
        if not isinstance(blueprint, list) or not 1 <= len(blueprint) <= 30:
            raise serializers.ValidationError({'blueprint': 'Add 1 to 30 scheme topic rows.'})
        from curriculum.models import CurriculumTopic
        seen = set()
        for row in blueprint:
            if not isinstance(row, dict) or not str(row.get('topic_id', '')).isdigit():
                raise serializers.ValidationError({'blueprint': 'Each row needs a scheme topic.'})
            topic_id = int(row['topic_id'])
            if topic_id in seen or not CurriculumTopic.objects.filter(pk=topic_id, archived=False,
                    week__plan__school=request.tenant, week__plan__term=term,
                    week__plan__subject=subject, week__plan__class_level=level).exists():
                raise serializers.ValidationError({'blueprint': 'Select distinct active topics in this term scheme.'})
            seen.add(topic_id)
            counts = [row.get('objective', 0), row.get('theory', 0)]
            if any(type(count) is not int or count < 0 or count > 100 for count in counts) or not sum(counts):
                raise serializers.ValidationError({'blueprint': 'Each row needs 1 to 100 objective or theory questions.'})
        if sum(row.get('objective', 0) + row.get('theory', 0) for row in blueprint) > 200:
            raise serializers.ValidationError({'blueprint': 'A paper may contain at most 200 questions.'})
        return attrs


class AssignmentSerializer(serializers.ModelSerializer):
    question_ids = serializers.PrimaryKeyRelatedField(source='questions', queryset=Question.objects.all(), many=True,
                                                      required=False, write_only=True)

    class Meta:
        model = OnlineAssignment
        fields = ['id', 'term', 'class_arm', 'subject', 'curriculum_topic', 'title', 'instructions',
                  'due_at', 'maximum', 'kind', 'component_key', 'status', 'question_snapshot', 'question_ids']
        read_only_fields = ['id', 'status', 'question_snapshot']

    def validate(self, attrs):
        request = self.context['request']
        assignment = self.instance
        term = attrs.get('term', getattr(assignment, 'term', None))
        arm = attrs.get('class_arm', getattr(assignment, 'class_arm', None))
        subject = attrs.get('subject', getattr(assignment, 'subject', None))
        validate_scope(request, term, subject, arm.class_level, arm)
        if assignment and assignment.status != 'draft':
            raise serializers.ValidationError('Published assignments cannot be edited.')
        if attrs.get('maximum', getattr(assignment, 'maximum', Decimal('10'))) <= 0:
            raise serializers.ValidationError({'maximum': 'Maximum must be positive.'})
        topic = attrs.get('curriculum_topic', getattr(assignment, 'curriculum_topic', None))
        if topic and (topic.week.plan.school_id != request.tenant.pk or topic.week.plan.term_id != term.pk or
                      topic.week.plan.subject_id != subject.pk or topic.week.plan.class_level_id != arm.class_level_id):
            raise serializers.ValidationError({'curriculum_topic': 'Choose a topic in this term scheme.'})
        kind = attrs.get('kind', getattr(assignment, 'kind', 'practice'))
        key = attrs.get('component_key', getattr(assignment, 'component_key', ''))
        if kind == 'graded':
            policy = policy_for(request.tenant, term)
            if not policy or key not in {c['key'] for c in policy.components}:
                raise serializers.ValidationError({'component_key': 'Choose a configured component for a graded assignment.'})
            if OnlineAssignment.objects.filter(school=request.tenant, term=term, class_arm=arm,
                    subject=subject, kind='graded', component_key=key).exclude(pk=getattr(assignment, 'pk', None)).exists():
                raise serializers.ValidationError({'component_key': 'One graded assignment may supply this component.'})
        elif key:
            raise serializers.ValidationError({'component_key': 'Practice assignments cannot map to the gradebook.'})
        questions = attrs.pop('questions', None)
        if questions is not None:
            if len(questions) > 50 or len({q.pk for q in questions}) != len(questions):
                raise serializers.ValidationError({'question_ids': 'Choose up to 50 distinct questions.'})
            if any(q.school_id != request.tenant.pk or q.subject_id != subject.pk or
                   q.class_level_id != arm.class_level_id or q.source != 'bank' or not q.is_active for q in questions):
                raise serializers.ValidationError({'question_ids': 'Choose active bank questions for this school, subject and class.'})
            from .serializers import QuestionSerializer
            attrs['question_snapshot'] = QuestionSerializer(questions, many=True).data
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        if request and request.user.role == 'student':
            data['question_snapshot'] = [
                {key: row[key] for key in ('id', 'question_text', 'question_image', 'question_type', 'options', 'marks') if key in row}
                for row in instance.question_snapshot
            ]
        return data
