"""Live, school-scoped operational read model for the Basic command centre."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import Holiday, Term
from attendance.models import AttendanceRecord, AttendanceSession
from curriculum.models import (
    AcademicResource, CurriculumApplicability, CurriculumPlan, CurriculumTopic,
    LessonPlan, SchoolAcademicStandard, TopicCoverage,
)
from enrollment.models import ClassArm, StaffProfile, Subject
from fees.billing import active_students
from fees.models import FeePayment, FeeSchedule
from gradebook.models import ScoreEntry
from cbt.models import OnlineAssignment, Question
from timetable.models import LessonRecord
from timetable.teaching import lesson_day_rows


def snapshot(school):
    terms = list(Term.objects.filter(session__school=school).select_related('session')
                 .order_by('-start_date').values('id', 'name', 'session__name', 'start_date', 'end_date', 'is_current'))
    return {
        'active_students': active_students(school).count(),
        'active_teachers': StaffProfile.objects.filter(school=school, employment_status='active',
            user__role='teacher', user__is_active=True).count(),
        'terms': terms,
    }


def attendance(school, term, day):
    if not term or not term.start_date <= day <= term.end_date:
        return {'state': 'outside_term'}
    holiday = Holiday.objects.filter(term=term, start_date__lte=day, end_date__gte=day).first()
    if holiday or day.weekday() >= 5:
        return {'state': 'non_teaching', 'holiday': holiday.name if holiday else 'Weekend'}
    expected = dict(active_students(school).filter(current_class__isnull=False)
                    .values('current_class_id').annotate(count=Count('id'))
                    .values_list('current_class_id', 'count'))
    # Starting a session pre-populates every student as present; only a finalized
    # register proves those default marks were reviewed by the teacher.
    sessions = AttendanceSession.objects.filter(school=school, term=term, date=day, is_finalized=True)
    marked = set(AttendanceRecord.objects.filter(attendance_session__in=sessions)
                 .values_list('attendance_session__class_arm_id', flat=True).distinct())
    status = AttendanceRecord.objects.filter(attendance_session__in=sessions).aggregate(
        **{key: Count('id', filter=Q(status=key)) for key in ('present', 'absent', 'late', 'excused')})
    examples = {}
    for key in ('absent', 'late'):
        examples[key] = list(AttendanceRecord.objects.filter(attendance_session__in=sessions, status=key)
            .values('student__student_profile__id', 'student__first_name', 'student__last_name',
                    'attendance_session__class_arm_id').distinct()[:8])
    missing_ids = sorted(set(expected) - marked)
    names = {arm.pk: arm.full_name for arm in ClassArm.objects.filter(school=school, pk__in=missing_ids)
             .select_related('class_level')}
    return {'state': 'recorded' if marked else 'no_records', 'marks': status,
            'classes_with_records': len(marked & set(expected)), 'classes_expected': len(expected),
            'classes_without_records': [{'id': pk, 'name': names.get(pk, str(pk))} for pk in missing_ids],
            'examples': examples}


def teaching(school, term, day):
    if not term or not term.start_date <= day <= term.end_date:
        return {'state': 'outside_term'}
    holiday = Holiday.objects.filter(term=term, start_date__lte=day, end_date__gte=day).first()
    if holiday or day.weekday() >= 5:
        return {'state': 'non_teaching', 'holiday': holiday.name if holiday else 'Weekend'}
    # Recurring timetable is not versioned. Older dates can report recorded outcomes only.
    if day < timezone.localdate() - timedelta(days=7):
        recorded = LessonRecord.objects.filter(school=school, term=term, date=day)
        counts = dict(recorded.values('outcome').annotate(total=Count('id')).values_list('outcome', 'total'))
        return {'state': 'recorded_history', 'counts': counts, 'scheduled': None, 'queue': []}
    rows, _ = lesson_day_rows(school, day, term.pk)
    counts = {key: sum(row['outcome'] == key for row in rows)
              for key in ('delivered', 'missed', 'cancelled', 'substituted')}
    counts['unresolved'] = sum(row['outcome'] is None for row in rows)
    return {'state': 'scheduled' if rows else 'no_lessons', 'scheduled': len(rows), 'counts': counts,
            'queue': [{'class_name': row['class_name'], 'subject_name': row['subject_name'],
                       'period_name': row['period_name'], 'slot_id': row['slot_id']}
                      for row in rows if row['outcome'] is None][:8]}


def curriculum(school, term):
    if not term:
        return {'state': 'no_term'}
    plans = list(CurriculumPlan.objects.filter(school=school, term=term)
                 .select_related('class_level', 'subject'))
    if not plans:
        return {'state': 'unconfigured', 'groups': []}
    arms = list(ClassArm.objects.filter(school=school, class_level_id__in={p.class_level_id for p in plans})
                .select_related('class_level'))
    topics = list(CurriculumTopic.objects.filter(week__plan_id__in=[p.pk for p in plans])
                  .values('id', 'week__plan_id', 'archived'))
    covered = defaultdict(lambda: defaultdict(set))
    history = set()
    coverage_rows = TopicCoverage.objects.filter(school=school, topic_id__in=[t['id'] for t in topics])
    for row in coverage_rows.values('topic_id', 'active', 'state', 'lesson__class_arm_id_snapshot'):
        history.add(row['topic_id'])
        if row['active']:
            covered[row['lesson__class_arm_id_snapshot']][row['topic_id']].add(row['state'])
    by_plan = defaultdict(list)
    for topic in topics:
        if not topic['archived'] or topic['id'] in history:
            by_plan[topic['week__plan_id']].append(topic['id'])
    groups = []
    for plan in plans:
        for arm in arms:
            if arm.class_level_id != plan.class_level_id:
                continue
            ids = by_plan[plan.pk]
            states = covered[arm.pk]
            done = sum('covered' in states[pk] for pk in ids)
            partial = sum('covered' not in states[pk] and bool(states[pk]) for pk in ids)
            groups.append({'class_arm': arm.pk, 'class_name': arm.full_name,
                'class_level': plan.class_level_id, 'subject': plan.subject_id,
                'subject_name': plan.subject.name, 'planned': len(ids), 'covered': done,
                'partial': partial, 'not_started': len(ids) - done - partial})
    return {'state': 'configured', 'groups': groups}



def academic_management(school, term):
    """Factual academic oversight: standards, planning, delivery evidence and assessment traceability."""
    if not term:
        return {'state': 'no_term'}

    standards = SchoolAcademicStandard.objects.filter(school=school).values('status').annotate(total=Count('id'))
    standard_counts = {row['status']: row['total'] for row in standards}
    applicability = CurriculumApplicability.objects.filter(school=school, session=term.session).count()

    plan_rows = LessonPlan.objects.filter(school=school, term=term)
    plan_counts = {row['status']: row['total'] for row in plan_rows.values('status').annotate(total=Count('id'))}
    plan_queue = list(plan_rows.filter(status__in=('submitted', 'reviewed')).select_related(
        'class_arm__class_level', 'subject', 'teacher', 'curriculum_topic'
    ).order_by('status', 'class_arm_id', 'subject_id').values(
        'id', 'status', 'class_arm_id', 'class_arm__class_level__name', 'class_arm__name',
        'subject_id', 'subject__name', 'teacher_id', 'teacher__first_name', 'teacher__last_name',
        'curriculum_topic_id', 'curriculum_topic__title', 'title'
    )[:20])

    resource_rows = AcademicResource.objects.filter(school=school)
    resource_counts = {row['status']: row['total'] for row in resource_rows.values('status').annotate(total=Count('id'))}
    resource_queue = list(resource_rows.filter(status__in=('submitted', 'reviewed')).select_related(
        'class_level', 'subject'
    ).order_by('status', 'class_level__order_index', 'subject__name').values(
        'id', 'status', 'class_level_id', 'class_level__name', 'subject_id', 'subject__name',
        'title', 'kind', 'revision'
    )[:20])

    plans = list(CurriculumPlan.objects.filter(school=school, term=term).select_related('class_level', 'subject'))
    topic_ids = list(CurriculumTopic.objects.filter(week__plan__in=plans, archived=False).values_list('id', flat=True))
    coverage = TopicCoverage.objects.filter(
        school=school, topic_id__in=topic_ids, active=True
    ).values('lesson__class_arm_id_snapshot', 'topic__week__plan_id').annotate(
        covered=Count('id', filter=Q(state='covered'), distinct=True),
        partial=Count('id', filter=Q(state='partial'), distinct=True),
    )
    coverage_map = {(row['lesson__class_arm_id_snapshot'], row['topic__week__plan_id']): row for row in coverage}

    groups = []
    for plan in plans:
        arms = ClassArm.objects.filter(school=school, class_level=plan.class_level).select_related('class_level')
        planned = CurriculumTopic.objects.filter(week__plan=plan, archived=False).count()
        question_count = Question.objects.filter(
            school=school, term=term, curriculum_topic__week__plan=plan, is_active=True
        ).count()
        assignment_count = OnlineAssignment.objects.filter(
            school=school, term=term, subject=plan.subject, curriculum_topic__week__plan=plan
        ).count()
        for arm in arms:
            actual = LessonRecord.objects.filter(
                school=school, term=term, class_arm_id_snapshot=arm.pk, subject_id_snapshot=plan.subject_id
            )
            outcomes = {row['outcome']: row['total'] for row in actual.values('outcome').annotate(total=Count('id'))}
            cov = coverage_map.get((arm.pk, plan.pk), {})
            groups.append({
                'class_arm': arm.pk, 'class_name': arm.full_name,
                'class_level': plan.class_level_id, 'subject': plan.subject_id, 'subject_name': plan.subject.name,
                'planned_topics': planned,
                'covered_evidence_rows': cov.get('covered', 0),
                'partial_evidence_rows': cov.get('partial', 0),
                'lesson_outcomes': outcomes,
                'assessment_questions_linked': question_count,
                'online_assignments_linked': assignment_count,
            })

    return {
        'state': 'configured' if plans else 'unconfigured',
        'applicable_curriculum_scopes': applicability,
        'standard_counts': standard_counts,
        'lesson_plan_counts': plan_counts,
        'lesson_plan_review_queue': plan_queue,
        'resource_counts': resource_counts,
        'resource_review_queue': resource_queue,
        'groups': groups,
        'note': 'Lesson plans and approved resources are planning/review evidence; LessonRecord and TopicCoverage remain delivery evidence.',
    }


def academic_history(school, term):
    """Compare factual academic records with the same term in the most recent earlier session."""
    if not term:
        return {'state': 'no_term'}

    previous = Term.objects.filter(
        session__school=school,
        name=term.name,
        session__start_date__lt=term.session.start_date,
    ).select_related('session').order_by('-session__start_date').first()

    def term_summary(target):
        if not target:
            return None
        plans = list(CurriculumPlan.objects.filter(school=school, term=target).select_related('class_level', 'subject'))
        plan_ids = [plan.pk for plan in plans]
        topics = list(CurriculumTopic.objects.filter(
            week__plan_id__in=plan_ids, archived=False
        ).values('id', 'week__plan_id'))
        topic_plan = {row['id']: row['week__plan_id'] for row in topics}
        coverage_rows = TopicCoverage.objects.filter(
            school=school, topic_id__in=topic_plan, active=True
        ).values('topic_id', 'state')
        covered_by_plan = defaultdict(set)
        partial_by_plan = defaultdict(set)
        for row in coverage_rows:
            plan_id = topic_plan.get(row['topic_id'])
            if row['state'] == 'covered':
                covered_by_plan[plan_id].add(row['topic_id'])
            elif row['topic_id'] not in covered_by_plan[plan_id]:
                partial_by_plan[plan_id].add(row['topic_id'])

        arm_levels = dict(ClassArm.objects.filter(school=school).values_list('id', 'class_level_id'))
        lesson_rows = LessonRecord.objects.filter(school=school, term=target).values(
            'class_arm_id_snapshot', 'subject_id_snapshot', 'outcome'
        ).annotate(total=Count('id'))
        lessons = defaultdict(lambda: defaultdict(int))
        for row in lesson_rows:
            level_id = arm_levels.get(row['class_arm_id_snapshot'])
            if level_id:
                lessons[(level_id, row['subject_id_snapshot'])][row['outcome']] += row['total']

        score_rows = ScoreEntry.objects.filter(
            school=school, term=target
        ).filter(Q(is_published=True) | Q(review_state='approved')).values(
            'class_arm__class_level_id', 'subject_id'
        ).annotate(records=Count('id'), average=Avg('total_score'))
        scores = {
            (row['class_arm__class_level_id'], row['subject_id']): {
                'records': row['records'],
                'average': str(row['average'].quantize(Decimal('0.01'))) if row['average'] is not None else None,
            }
            for row in score_rows
        }

        resource_counts = {
            (row['class_level_id'], row['subject_id']): row['total']
            for row in AcademicResource.objects.filter(
                school=school, status=AcademicResource.Status.APPROVED,
                approved_at__date__lte=target.end_date
            ).values('class_level_id', 'subject_id').annotate(total=Count('id'))
        }
        applicability = {
            (row['class_level_id'], row['subject_id']): {
                'version_id': row['curriculum_version_id'],
                'source': row['curriculum_version__source__name'],
                'version': row['curriculum_version__label'],
            }
            for row in CurriculumApplicability.objects.filter(
                school=school, session=target.session
            ).values(
                'class_level_id', 'subject_id', 'curriculum_version_id',
                'curriculum_version__source__name', 'curriculum_version__label'
            )
        }
        approved_standards = {}
        for row in SchoolAcademicStandard.objects.filter(
            school=school, status=SchoolAcademicStandard.Status.APPROVED,
            approved_at__date__lte=target.end_date,
        ).order_by('class_level_id', 'subject_id', 'curriculum_version_id', '-revision').values(
            'class_level_id', 'subject_id', 'curriculum_version_id', 'title', 'revision'
        ):
            key = (row['class_level_id'], row['subject_id'], row['curriculum_version_id'])
            approved_standards.setdefault(key, {'title': row['title'], 'revision': row['revision']})

        groups = []
        topics_per_plan = defaultdict(int)
        for row in topics:
            topics_per_plan[row['week__plan_id']] += 1
        for plan in plans:
            key = (plan.class_level_id, plan.subject_id)
            covered = len(covered_by_plan[plan.pk])
            partial = len(partial_by_plan[plan.pk] - covered_by_plan[plan.pk])
            groups.append({
                'class_level': plan.class_level_id,
                'class_level_name': plan.class_level.name,
                'subject': plan.subject_id,
                'subject_name': plan.subject.name,
                'planned_topics': topics_per_plan[plan.pk],
                'covered_topics': covered,
                'partial_topics': partial,
                'lesson_outcomes': dict(lessons.get(key, {})),
                'approved_resources': resource_counts.get(key, 0),
                'result_records': scores.get(key, {}).get('records', 0),
                'result_average': scores.get(key, {}).get('average'),
                'curriculum': applicability.get(key),
                'academic_standard': approved_standards.get(
                    (plan.class_level_id, plan.subject_id, (applicability.get(key) or {}).get('version_id'))
                ),
            })
        return {
            'term': target.pk,
            'term_name': target.name,
            'session': target.session_id,
            'session_name': target.session.name,
            'groups': groups,
        }

    current = term_summary(term)
    prior = term_summary(previous)
    if not previous:
        return {
            'state': 'no_previous_term',
            'current': current,
            'previous': None,
            'note': 'No earlier matching term is available. Historical comparison uses recorded evidence only.',
        }

    current_map = {(row['class_level'], row['subject']): row for row in current['groups']}
    previous_map = {(row['class_level'], row['subject']): row for row in prior['groups']}
    keys = sorted(set(current_map) | set(previous_map))
    comparison = []
    for key in keys:
        now, before = current_map.get(key), previous_map.get(key)
        comparison.append({
            'class_level': (now or before)['class_level'],
            'class_level_name': (now or before)['class_level_name'],
            'subject': (now or before)['subject'],
            'subject_name': (now or before)['subject_name'],
            'current': now,
            'previous': before,
        })
    return {
        'state': 'comparable',
        'current': current,
        'previous': prior,
        'comparison': comparison,
        'note': 'Counts and averages describe recorded evidence for each session; they are not teacher-quality or school-quality scores.',
    }

def results(school, term):
    if not term:
        return {'state': 'no_term'}
    rows = ScoreEntry.objects.filter(school=school, term=term).values('class_arm_id', 'subject_id', 'review_state', 'is_published').annotate(total=Count('id'))
    counts = {'submitted': 0, 'approved': 0, 'published': 0}
    groups = defaultdict(lambda: {'submitted': 0, 'approved': 0, 'published': 0})
    for row in rows:
        state = 'published' if row['is_published'] else row['review_state']
        if state in counts:
            counts[state] += row['total']
            groups[(row['class_arm_id'], row['subject_id'])][state] += row['total']
    names = {arm.pk: arm.full_name for arm in ClassArm.objects.filter(school=school, pk__in=[key[0] for key in groups])
             .select_related('class_level')}
    subjects = dict(Subject.objects.filter(school=school, pk__in=[key[1] for key in groups]).values_list('id', 'name'))
    return {'state': 'recorded' if groups else 'no_submissions', 'counts': counts,
            'groups': [{'class_arm': key[0], 'class_name': names.get(key[0], str(key[0])),
                        'subject': key[1], 'subject_name': subjects.get(key[1], str(key[1])), **data}
                       for key, data in groups.items()]}


def finance(school, term):
    if not term:
        return {'state': 'no_term'}
    schedules = FeeSchedule.objects.filter(school=school, term=term)
    payments = FeePayment.objects.filter(school=school, fee_schedule__in=schedules)
    from enrollment.models import StudentProfile
    from fees.ledger import balance_accounts
    students = StudentProfile.objects.filter(school=school, status='active')
    known = balance_accounts(school, students)
    unknown = students.count() - known.count()
    debtors = known.filter(balance__gt=0)
    return {'state': 'unconfigured' if not schedules.exists() else 'partial' if unknown else 'configured',
            'configured_schedules': schedules.count(),
            'recorded_payments': payments.count(),
            'recorded_amount': str(payments.aggregate(total=Sum('amount_paid'))['total'] or 0),
            'known_outstanding': str(debtors.aggregate(total=Sum('balance'))['total'] or 0),
            'debtor_count': debtors.count(), 'unknown_accounts': unknown}


SECTIONS = {'snapshot': snapshot, 'attendance': attendance, 'teaching': teaching,
            'curriculum': curriculum, 'academic_management': academic_management,
            'academic_history': academic_history, 'results': results, 'finance': finance}


class PrincipalOperationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school, user = getattr(request, 'tenant', None), request.user
        if not school or not user.is_active or user.must_change_password or user.school_id != school.pk or user.role not in ('school_admin', 'principal'):
            return Response({'detail': 'School management access required.'}, status=403)
        section = request.query_params.get('section', 'snapshot')
        if section not in SECTIONS:
            return Response({'section': 'Choose a valid section.'}, status=400)
        raw_day = request.query_params.get('date')
        try:
            day = date.fromisoformat(raw_day) if raw_day else timezone.localdate()
        except ValueError:
            return Response({'date': 'Use a valid ISO date.'}, status=400)
        if day > timezone.localdate():
            return Response({'date': 'Choose today or an earlier date.'}, status=400)
        raw_term = request.query_params.get('term')
        if raw_term and (not raw_term.isdigit() or int(raw_term) < 1):
            return Response({'term': 'Choose a valid term.'}, status=400)
        term = (Term.objects.filter(session__school=school, pk=raw_term).first() if raw_term else
                Term.objects.filter(session__school=school, start_date__lte=day, end_date__gte=day).first())
        if raw_term and not term:
            return Response({'term': 'Choose a term in this school.'}, status=400)
        if section in ('attendance', 'teaching') and term and not term.start_date <= day <= term.end_date:
            return Response({'date': 'Choose a date inside the selected term.'}, status=400)
        if section == 'snapshot':
            data = snapshot(school)
        elif section in ('attendance', 'teaching'):
            data = SECTIONS[section](school, term, day)
        else:
            data = SECTIONS[section](school, term)
        return Response({'section': section, 'date': day, 'term': term.pk if term else None, **data})
