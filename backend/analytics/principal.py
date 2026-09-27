"""Live, school-scoped operational read model for the Basic command centre."""
from collections import defaultdict
from datetime import date, timedelta

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import Holiday, Term
from attendance.models import AttendanceRecord, AttendanceSession
from curriculum.models import CurriculumPlan, CurriculumTopic, TopicCoverage
from enrollment.models import ClassArm, StaffProfile, Subject
from fees.billing import active_students
from fees.models import FeePayment, FeeSchedule
from gradebook.models import ScoreEntry
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
    return {'state': 'configured' if schedules.exists() else 'unconfigured',
            'configured_schedules': schedules.count(),
            'recorded_payments': payments.count(),
            'recorded_amount': str(payments.aggregate(total=Sum('amount_paid'))['total'] or 0)}


SECTIONS = {'snapshot': snapshot, 'attendance': attendance, 'teaching': teaching,
            'curriculum': curriculum, 'results': results, 'finance': finance}


class PrincipalOperationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school, user = getattr(request, 'tenant', None), request.user
        if not school or not user.is_active or user.must_change_password or user.school_id != school.pk or user.role != 'school_admin':
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
