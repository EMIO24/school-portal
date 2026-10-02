"""School plans and evidence of delivery, with lesson context as the write boundary."""
from collections import defaultdict

from django.db import IntegrityError, transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.school_access import require_assignment
from academics.models import Holiday, Term
from enrollment.models import ClassArm, ClassLevel, Subject, SubjectAssignment
from tenants.security import audit
from timetable.models import LessonRecord, TimetableEntry
from .models import CurriculumPlan, CurriculumTopic, CurriculumWeek, LearningObjective, TopicCoverage


def allowed(request):
    user, school = request.user, getattr(request, 'tenant', None)
    return bool(school and user.is_authenticated and user.is_active and not user.must_change_password
                and user.school_id == school.pk and user.role in ('school_admin', 'principal', 'teacher', 'class_teacher'))


def positive(value):
    try:
        number = int(value)
        return number if number > 0 and str(number) == str(value) else None
    except (TypeError, ValueError):
        return None


def context(request, data):
    school = request.tenant
    term = Term.objects.filter(pk=positive(data.get('term')), session__school=school).first()
    level = ClassLevel.objects.filter(pk=positive(data.get('class_level')), school=school).first()
    subject = Subject.objects.filter(pk=positive(data.get('subject')), school=school).first()
    return term, level, subject


def can_read(request, term, level, subject, arm_id):
    if request.user.role in ('school_admin', 'principal'):
        return True
    arm = ClassArm.objects.filter(pk=positive(arm_id), school=request.tenant, class_level=level).first()
    if not arm:
        return False
    from rest_framework.exceptions import PermissionDenied
    try:
        require_assignment(request, arm.pk, term.pk, subject.pk)
    except PermissionDenied:
        return False
    return True


def plan_data(plan, arm_id=None):
    weeks = list(plan.weeks.prefetch_related('topics__objectives').all())
    topics = [topic for week in weeks for topic in week.topics.all()]
    history_ids = set(TopicCoverage.objects.filter(topic_id__in=[t.pk for t in topics]).values_list('topic_id', flat=True)) if topics else set()
    states = defaultdict(set)
    evidence = defaultdict(list)
    if arm_id and topics:
        for row in TopicCoverage.objects.filter(
            school=plan.school, topic_id__in=[t.pk for t in topics], active=True,
            lesson__class_arm_id_snapshot=arm_id,
        ).order_by('lesson__date', 'lesson_id').values('topic_id', 'state', 'lesson_id', 'lesson__date'):
            states[row['topic_id']].add(row['state'])
            evidence[row['topic_id']].append({'lesson': row['lesson_id'], 'date': row['lesson__date'], 'state': row['state']})
    summary = {'total': 0, 'not_started': 0, 'partial': 0, 'covered': 0}
    result = []
    for week in weeks:
        rendered = []
        week_summary = {'total': 0, 'not_started': 0, 'partial': 0, 'covered': 0}
        for topic in week.topics.all():
            state = 'covered' if 'covered' in states[topic.pk] else 'partial' if states[topic.pk] else 'not_started'
            if not topic.archived or topic.pk in history_ids:
                summary['total'] += 1
                summary[state] += 1
                week_summary['total'] += 1
                week_summary[state] += 1
            rendered.append({'id': topic.pk, 'title': topic.title, 'description': topic.description,
                             'position': topic.position, 'archived': topic.archived, 'locked': topic.pk in history_ids, 'state': state,
                             'evidence': evidence[topic.pk],
                             'objectives': [{'id': o.pk, 'text': o.text, 'position': o.position}
                                            for o in topic.objectives.all()]})
        result.append({'id': week.pk, 'number': week.number, 'label': week.label, 'topics': rendered, 'summary': week_summary})
    return {'id': plan.pk, 'term': plan.term_id, 'class_level': plan.class_level_id,
            'subject': plan.subject_id, 'weeks': result, 'summary': summary}


def holidays(term):
    return list(Holiday.objects.filter(term=term).values('id', 'name', 'start_date', 'end_date', 'holiday_type'))


class AssignedPlansView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not allowed(request) or request.user.role not in ('teacher', 'class_teacher'):
            return Response({'detail': 'Assigned teacher access required.'}, status=403)
        assignments = SubjectAssignment.objects.filter(school=request.tenant, teacher__user=request.user,
            teacher__employment_status='active').select_related('term__session', 'class_arm__class_level', 'subject')
        return Response({'assignments': [{'term': a.term_id, 'term_name': str(a.term),
            'class_arm': a.class_arm_id, 'class_name': a.class_arm.full_name,
            'class_level': a.class_arm.class_level_id, 'subject': a.subject_id, 'subject_name': a.subject.name}
            for a in assignments]})


class PlanView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not allowed(request):
            return Response({'detail': 'School curriculum access required.'}, status=403)
        term, level, subject = context(request, request.query_params)
        if not all((term, level, subject)):
            return Response({'detail': 'Choose a term, class level and subject in this school.'}, status=400)
        arm_id = request.query_params.get('class_arm')
        if not can_read(request, term, level, subject, arm_id):
            return Response({'detail': 'This curriculum is not assigned to you.'}, status=403)
        if arm_id and not ClassArm.objects.filter(pk=positive(arm_id), school=request.tenant, class_level=level).exists():
            return Response({'class_arm': 'Choose a class in this level.'}, status=400)
        plan = CurriculumPlan.objects.filter(school=request.tenant, term=term, class_level=level, subject=subject).first()
        return Response({'plan': plan_data(plan, positive(arm_id)) if plan else None, 'holidays': holidays(term)})

    @transaction.atomic
    def post(self, request):
        if not allowed(request) or request.user.role != 'school_admin':
            return Response({'detail': 'School administrator access required.'}, status=403)
        term, level, subject = context(request, request.data)
        week_no, position = positive(request.data.get('week')), positive(request.data.get('position'))
        title, description = request.data.get('title'), request.data.get('description', '')
        label = request.data.get('week_label', '')
        objectives = request.data.get('objectives', [])
        if not all((term, level, subject)) or not week_no or week_no > 52 or not position or position > 100:
            return Response({'detail': 'Choose a valid school context, week and position.'}, status=400)
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 180 or not isinstance(description, str) or len(description) > 500 or not isinstance(label, str) or len(label) > 80:
            return Response({'detail': 'Check the topic title, description and week label.'}, status=400)
        if not isinstance(objectives, list) or len(objectives) > 30 or any(not isinstance(o, str) or not o.strip() or len(o.strip()) > 300 for o in objectives):
            return Response({'objectives': 'Provide up to 30 concise objectives.'}, status=400)
        if len({o.strip().casefold() for o in objectives}) != len(objectives):
            return Response({'objectives': 'Duplicate objectives are not allowed.'}, status=400)
        plan, _ = CurriculumPlan.objects.get_or_create(school=request.tenant, term=term, class_level=level, subject=subject)
        week, _ = CurriculumWeek.objects.get_or_create(plan=plan, number=week_no, defaults={'label': label})
        if CurriculumTopic.objects.filter(week=week, position=position).exists():
            return Response({'position': 'That position already has a topic.'}, status=409)
        try:
            with transaction.atomic():
                topic = CurriculumTopic.objects.create(week=week, title=title.strip(), description=description, position=position)
                LearningObjective.objects.bulk_create([LearningObjective(topic=topic, text=o.strip(), position=i)
                                                       for i, o in enumerate(objectives, 1)])
        except IntegrityError:
            return Response({'position': 'That position already has a topic.'}, status=409)
        audit(request, 'curriculum.topic_created', target=f'topic:{topic.pk}', details={'school_id': request.tenant.pk})
        return Response({'topic': topic.pk}, status=201)


class TopicView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, topic_id):
        if not allowed(request) or request.user.role != 'school_admin':
            return Response({'detail': 'School administrator access required.'}, status=403)
        topic = CurriculumTopic.objects.select_for_update().filter(pk=topic_id, week__plan__school=request.tenant).first()
        if not topic:
            return Response({'detail': 'Topic not found.'}, status=404)
        if TopicCoverage.objects.filter(topic=topic).exists() and any(k in request.data for k in ('title', 'description', 'position', 'objectives', 'week')):
            return Response({'detail': 'This topic has lesson history. Archive it; preserve its taught content.'}, status=409)
        title = request.data.get('title', topic.title)
        description = request.data.get('description', topic.description)
        position = positive(request.data.get('position', topic.position))
        archived = request.data.get('archived', topic.archived)
        objectives = request.data.get('objectives')
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 180 or not isinstance(description, str) or len(description) > 500 or not position or position > 100 or type(archived) is not bool:
            return Response({'detail': 'Check topic fields.'}, status=400)
        if objectives is not None and (not isinstance(objectives, list) or len(objectives) > 30 or any(not isinstance(o, str) or not o.strip() or len(o.strip()) > 300 for o in objectives) or len({o.strip().casefold() for o in objectives}) != len(objectives)):
            return Response({'objectives': 'Provide distinct concise objectives.'}, status=400)
        if position != topic.position and CurriculumTopic.objects.filter(week=topic.week, position=position).exists():
            return Response({'position': 'That position already has a topic.'}, status=409)
        before = (topic.title, topic.description, topic.position, topic.archived, list(topic.objectives.values_list('text', flat=True)))
        after = (title.strip(), description, position, archived, [o.strip() for o in objectives] if objectives is not None else before[4])
        if before == after:
            return Response({'topic': topic.pk})
        topic.title, topic.description, topic.position, topic.archived = after[:4]
        topic.save()
        if objectives is not None:
            topic.objectives.all().delete()
            LearningObjective.objects.bulk_create([LearningObjective(topic=topic, text=o, position=i) for i, o in enumerate(after[4], 1)])
        audit(request, 'curriculum.topic_changed', target=f'topic:{topic.pk}', details={'school_id': request.tenant.pk, 'changed_fields': [k for k, b, a in zip(('title','description','position','archived','objectives'), before, after) if b != a]})
        return Response({'topic': topic.pk})


def lesson_access(request, lesson):
    if request.user.role == 'school_admin':
        return True
    if lesson.outcome == 'substituted':
        return lesson.actual_teacher_id == request.user.pk
    return lesson.actual_teacher_id == request.user.pk and lesson.scheduled_teacher_id == request.user.pk


def lesson_plan(request, lesson):
    arm = ClassArm.objects.filter(pk=lesson.class_arm_id_snapshot, school=request.tenant).select_related('class_level').first()
    if not arm or not lesson.term_id or not Term.objects.filter(pk=lesson.term_id, session__school=request.tenant).exists():
        return None
    return CurriculumPlan.objects.filter(school=request.tenant, term_id=lesson.term_id,
                                         class_level=arm.class_level, subject_id=lesson.subject_id_snapshot).first()


class LessonCurriculumView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        if not allowed(request):
            return Response({'detail': 'School curriculum access required.'}, status=403)
        lesson = LessonRecord.objects.filter(pk=lesson_id, school=request.tenant).first()
        if not lesson or not lesson_access(request, lesson):
            return Response({'detail': 'Lesson not found.'}, status=404)
        plan = lesson_plan(request, lesson)
        records = TopicCoverage.objects.filter(school=request.tenant, lesson=lesson).values('topic_id', 'state', 'note', 'active', 'revision')
        return Response({'lesson': lesson.pk, 'outcome': lesson.outcome, 'holidays': holidays(lesson.term) if lesson.term_id else [],
                         'plan': plan_data(plan, lesson.class_arm_id_snapshot) if plan else None,
                         'coverage': {row['topic_id']: row for row in records}})


class ScheduledCurriculumView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slot_id):
        if not allowed(request):
            return Response({'detail': 'School curriculum access required.'}, status=403)
        slot = TimetableEntry.objects.filter(pk=slot_id, school=request.tenant).select_related('term__session', 'class_arm__class_level').first()
        if not slot:
            return Response({'detail': 'Scheduled lesson not found.'}, status=404)
        if request.user.role in ('teacher', 'class_teacher'):
            if slot.teacher_id != request.user.pk or not can_read(request, slot.term, slot.class_arm.class_level, slot.subject, slot.class_arm_id):
                return Response({'detail': 'This curriculum is not assigned to you.'}, status=403)
        plan = CurriculumPlan.objects.filter(school=request.tenant, term=slot.term,
            class_level=slot.class_arm.class_level, subject=slot.subject).first()
        return Response({'lesson': None, 'outcome': None, 'coverage': {},
                         'plan': plan_data(plan, slot.class_arm_id) if plan else None,
                         'holidays': holidays(slot.term)})


class CoverageView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request, lesson_id, topic_id):
        if not allowed(request):
            return Response({'detail': 'School curriculum access required.'}, status=403)
        lesson = LessonRecord.objects.select_for_update().filter(pk=lesson_id, school=request.tenant).first()
        if not lesson or not lesson_access(request, lesson):
            return Response({'detail': 'Lesson not found.'}, status=404)
        if lesson.outcome not in ('delivered', 'substituted'):
            return Response({'detail': 'Record a delivered lesson before curriculum coverage.'}, status=409)
        plan = lesson_plan(request, lesson)
        topic = CurriculumTopic.objects.select_for_update().filter(pk=topic_id, week__plan=plan).first() if plan else None
        if not topic or topic.archived:
            return Response({'detail': 'Topic is not in this lesson curriculum.'}, status=400)
        state, note, revision = request.data.get('state'), request.data.get('note', ''), request.data.get('revision')
        if state not in TopicCoverage.State.values or not isinstance(note, str) or len(note) > 300 or type(revision) is not int or revision < 0:
            return Response({'detail': 'Choose partial or covered, an optional short note, and the current revision.'}, status=400)
        record = TopicCoverage.objects.select_for_update().filter(lesson=lesson, topic=topic).first()
        if record:
            if (record.state, record.note, record.active) == (state, note, True):
                return Response({'state': state, 'note': note, 'revision': record.revision, 'active': True})
            if record.revision != revision:
                return Response({'detail': 'Coverage changed. Reload before saving.'}, status=409)
            before = {'state': record.state, 'active': record.active}
            record.state, record.note, record.active = state, note, True
            record.revision += 1
            record.recorded_by = request.user
            record.save()
            status_code = 200
        else:
            if revision != 0:
                return Response({'detail': 'Reload before saving.'}, status=409)
            try:
                with transaction.atomic():
                    record = TopicCoverage.objects.create(school=request.tenant, lesson=lesson, topic=topic,
                                                          state=state, note=note, recorded_by=request.user)
            except IntegrityError:
                current = TopicCoverage.objects.get(lesson=lesson, topic=topic)
                if (current.state, current.note, current.active) == (state, note, True):
                    return Response({'state': state, 'note': note, 'revision': current.revision, 'active': True})
                return Response({'detail': 'Coverage changed. Reload before saving.'}, status=409)
            before, status_code = None, 201
        audit(request, 'curriculum.coverage_saved', target=f'coverage:{record.pk}', details={
            'school_id': request.tenant.pk, 'lesson_id': lesson.pk, 'topic_id': topic.pk,
            'before': before, 'after': state, 'revision': record.revision})
        return Response({'state': state, 'note': note, 'revision': record.revision, 'active': True}, status=status_code)

    @transaction.atomic
    def delete(self, request, lesson_id, topic_id):
        if not allowed(request):
            return Response({'detail': 'School curriculum access required.'}, status=403)
        lesson = LessonRecord.objects.select_for_update().filter(pk=lesson_id, school=request.tenant).first()
        if not lesson or not lesson_access(request, lesson):
            return Response({'detail': 'Lesson not found.'}, status=404)
        record = TopicCoverage.objects.select_for_update().filter(school=request.tenant, lesson=lesson, topic_id=topic_id).first()
        if not record:
            return Response({'detail': 'Coverage not found.'}, status=404)
        revision = request.data.get('revision')
        if not record.active:
            return Response({'active': False, 'revision': record.revision})
        if type(revision) is not int or revision != record.revision:
            return Response({'detail': 'Coverage changed. Reload before removing.'}, status=409)
        record.active = False
        record.revision += 1
        record.recorded_by = request.user
        record.save()
        audit(request, 'curriculum.coverage_removed', target=f'coverage:{record.pk}', details={
            'school_id': request.tenant.pk, 'lesson_id': lesson.pk, 'topic_id': topic_id,
            'before': record.state, 'after': None, 'revision': record.revision})
        return Response({'active': False, 'revision': record.revision})
