"""Dated teaching outcomes on top of the existing recurring timetable."""

from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import Holiday, Term
from enrollment.models import StaffProfile
from tenants.security import audit
from .models import LessonRecord, TimetableEntry


def _name(user):
    return (user.get_full_name() or user.email or str(user.pk)) if user else ''


def _day(raw):
    try:
        value = date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return value


def _authorized(request):
    user, school = request.user, getattr(request, 'tenant', None)
    return (user.is_authenticated and user.is_active and not user.must_change_password
            and school and user.school_id == school.pk and user.role in ('teacher', 'school_admin'))


def _active_teacher(user, school):
    return (user and user.is_active and user.role == 'teacher' and user.school_id == school.pk
            and StaffProfile.objects.filter(user=user, school=school, employment_status='active').exists())


def _row(record=None, slot=None):
    if record:
        return {
            'id': record.pk, 'slot_id': record.slot_id, 'date': record.date.isoformat(), 'term': record.term_id,
            'class_arm': record.class_arm_id_snapshot, 'class_name': record.class_name,
            'subject': record.subject_id_snapshot, 'subject_name': record.subject_name,
            'period_name': record.period_name, 'period_start': record.period_start.isoformat(timespec='minutes'),
            'period_end': record.period_end.isoformat(timespec='minutes'),
            'scheduled_teacher': record.scheduled_teacher_id,
            'scheduled_teacher_name': record.scheduled_teacher_name,
            'actual_teacher': record.actual_teacher_id, 'actual_teacher_name': record.actual_teacher_name,
            'outcome': record.outcome, 'note': record.note, 'revision': record.revision,
            'recorded_by': record.recorded_by_id, 'recorded_at': record.recorded_at,
            'updated_at': record.updated_at,
        }
    return {
        'id': None, 'slot_id': slot.pk, 'date': None, 'term': slot.term_id,
        'class_arm': slot.class_arm_id, 'class_name': slot.class_arm.full_name,
        'subject': slot.subject_id, 'subject_name': slot.subject.name,
        'period_name': slot.period.name, 'period_start': slot.period.start_time.isoformat(timespec='minutes'),
        'period_end': slot.period.end_time.isoformat(timespec='minutes'),
        'scheduled_teacher': slot.teacher_id, 'scheduled_teacher_name': _name(slot.teacher),
        'actual_teacher': None, 'actual_teacher_name': '',
        'outcome': None, 'note': '', 'revision': 0,
        'recorded_by': None, 'recorded_at': None, 'updated_at': None,
    }


class LessonDayView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _authorized(request):
            return Response({'detail': 'School teaching access required.'}, status=403)
        day = _day(request.query_params.get('date'))
        if day is None:
            return Response({'date': 'Use a valid ISO date.'}, status=400)
        if request.query_params.get('term') and not request.query_params['term'].isdigit():
            return Response({'term': 'Choose a valid term.'}, status=400)
        school = request.tenant
        terms = Term.objects.filter(session__school=school, start_date__lte=day, end_date__gte=day)
        if request.query_params.get('term'):
            terms = terms.filter(pk=request.query_params['term'])
        term_ids = list(terms.values_list('pk', flat=True))
        holiday_terms = set(Holiday.objects.filter(
            term_id__in=term_ids, start_date__lte=day, end_date__gte=day
        ).values_list('term_id', flat=True))
        weekday = ('MON', 'TUE', 'WED', 'THU', 'FRI', None, None)[day.weekday()]
        slots = []
        if weekday:
            slots = list(TimetableEntry.objects.filter(
                school=school, term_id__in=[pk for pk in term_ids if pk not in holiday_terms],
                day_of_week=weekday, period__is_break=False
            ).select_related('term', 'class_arm__class_level', 'subject', 'period', 'teacher')
                         .order_by('period__order_index', 'class_arm_id'))
        records = LessonRecord.objects.filter(school=school, date=day).select_related('actual_teacher')
        if request.query_params.get('term'):
            records = records.filter(term_id=request.query_params['term'])
        if request.user.role == 'teacher':
            slots = [s for s in slots if s.teacher_id == request.user.pk]
            records = records.filter(scheduled_teacher_id=request.user.pk) | records.filter(actual_teacher_id=request.user.pk)
        by_slot = {r.slot_id: r for r in records}
        recorded_positions = {
            (r.term_id, r.class_arm_id_snapshot, r.period_start, r.period_end) for r in by_slot.values()
        }
        rows = []
        for slot in slots:
            recorded = by_slot.pop(slot.pk, None)
            if recorded:
                rows.append(_row(recorded))
            elif (slot.term_id, slot.class_arm_id, slot.period.start_time, slot.period.end_time) not in recorded_positions:
                rows.append(_row(slot=slot))
        rows.extend(_row(record=r) for r in by_slot.values())
        for row in rows:
            row['date'] = day.isoformat()
        for field in ('class_arm', 'teacher', 'subject'):
            raw = request.query_params.get(field)
            if raw:
                if not raw.isdigit():
                    return Response({field: 'Choose a valid ID.'}, status=400)
                key = 'scheduled_teacher' if field == 'teacher' else field
                rows = [r for r in rows if r[key] == int(raw) or
                        (field == 'teacher' and r['actual_teacher'] == int(raw))]
        outcome = request.query_params.get('outcome')
        if outcome:
            if outcome not in ('delivered', 'missed', 'cancelled', 'substituted', 'unresolved'):
                return Response({'outcome': 'Choose a valid outcome.'}, status=400)
            rows = [r for r in rows if (r['outcome'] or 'unresolved') == outcome]
        rows.sort(key=lambda r: (r['period_start'], r['class_name'], r['slot_id']))
        return Response({'date': day.isoformat(), 'holiday': bool(holiday_terms), 'lessons': rows})


class LessonOutcomeView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def put(self, request, slot_id, lesson_date):
        if not _authorized(request):
            return Response({'detail': 'School teaching access required.'}, status=403)
        if not isinstance(request.data, dict):
            return Response({'detail': 'Submit one lesson outcome.'}, status=400)
        day = _day(lesson_date)
        if not day or day > timezone.localdate():
            return Response({'date': 'Choose today or an earlier date.'}, status=400)
        school, user = request.tenant, request.user
        record = LessonRecord.objects.select_for_update().filter(school=school, slot_id=slot_id, date=day).first()
        slot = TimetableEntry.objects.filter(school=school, pk=slot_id).select_related(
            'term__session', 'class_arm', 'subject', 'period', 'teacher'
        ).first()
        if not record and not slot:
            return Response({'detail': 'Scheduled lesson not found.'}, status=404)
        term = record.term if record else slot.term
        if not term or term.session.school_id != school.pk or not term.start_date <= day <= term.end_date:
            return Response({'date': 'Date is outside this school term.'}, status=400)
        if not record and (slot.day_of_week != ('MON', 'TUE', 'WED', 'THU', 'FRI', None, None)[day.weekday()]
                           or slot.period.is_break or Holiday.objects.filter(
                               term=term, start_date__lte=day, end_date__gte=day).exists()):
            return Response({'date': 'No scheduled lesson occurs on this date.'}, status=400)
        scheduled_id = record.scheduled_teacher_id if record else slot.teacher_id
        if user.role == 'teacher':
            if day != timezone.localdate() or scheduled_id != user.pk or not _active_teacher(user, school):
                return Response({'detail': 'Only your current scheduled lessons can be recorded.'}, status=403)
        outcome = request.data.get('outcome')
        if outcome not in LessonRecord.Outcome.values:
            return Response({'outcome': 'Choose a valid lesson outcome.'}, status=400)
        if user.role == 'teacher' and outcome not in ('delivered', 'missed'):
            return Response({'detail': 'A school administrator must cancel or assign a substitute.'}, status=403)
        note = request.data.get('note', '')
        if not isinstance(note, str) or len(note) > 500:
            return Response({'note': 'Enter at most 500 characters.'}, status=400)
        actual_id = request.data.get('actual_teacher')
        if outcome == 'substituted':
            if user.role != 'school_admin' or type(actual_id) is not int:
                return Response({'actual_teacher': 'Select an active substitute teacher.'}, status=400)
            from accounts.models import CustomUser
            actual = CustomUser.objects.filter(pk=actual_id, school=school, role='teacher', is_active=True).first()
            if not _active_teacher(actual, school) or actual_id == scheduled_id:
                return Response({'actual_teacher': 'Select another active teacher in this school.'}, status=400)
        else:
            if actual_id is not None:
                return Response({'actual_teacher': 'Only substituted lessons accept a substitute.'}, status=400)
            actual = None
            if outcome == 'delivered' and scheduled_id:
                from accounts.models import CustomUser
                actual = CustomUser.objects.filter(pk=scheduled_id, school=school).first()
            if outcome == 'delivered' and actual is None:
                return Response({'outcome': 'Assign an expected teacher before recording delivery.'}, status=400)
        revision = request.data.get('revision')
        if type(revision) is not int or revision < 0:
            return Response({'revision': 'Include the revision shown in the lesson list.'}, status=400)
        if record:
            if (record.outcome, record.note, record.actual_teacher_id) == (outcome, note, actual.pk if actual else None):
                return Response(_row(record))
            if revision != record.revision:
                return Response({'detail': 'The lesson changed. Reload it before saving.'}, status=409)
            if outcome in ('missed', 'cancelled'):
                from curriculum.models import TopicCoverage
                if TopicCoverage.objects.filter(lesson=record, active=True).exists():
                    return Response({'detail': 'Remove active curriculum coverage before changing this lesson to missed or cancelled.'}, status=409)
            if user.role == 'teacher' and record.recorded_by_id != user.pk:
                return Response({'detail': 'Ask a school administrator to correct this outcome.'}, status=403)
            changed = [name for name, before, after in (
                ('outcome', record.outcome, outcome), ('note', record.note, note),
                ('actual_teacher', record.actual_teacher_id, actual.pk if actual else None)
            ) if before != after]
            old_outcome = record.outcome
            record.outcome, record.note, record.actual_teacher = outcome, note, actual
            record.actual_teacher_name = _name(actual)
            record.revision += 1
            record.save()
            action = 'lesson.outcome_corrected'
        else:
            if revision != 0:
                return Response({'detail': 'Reload the scheduled lesson before saving.'}, status=409)
            try:
                with transaction.atomic():
                    record = LessonRecord.objects.create(
                        school=school, timetable_entry=slot, slot_id=slot.pk, date=day, term=term,
                        term_name=str(term), class_arm_id_snapshot=slot.class_arm_id,
                        class_name=slot.class_arm.full_name, subject_id_snapshot=slot.subject_id,
                        subject_name=slot.subject.name, period_name=slot.period.name,
                        period_start=slot.period.start_time, period_end=slot.period.end_time,
                        scheduled_teacher_id=slot.teacher_id, scheduled_teacher_name=_name(slot.teacher),
                        actual_teacher=actual, actual_teacher_name=_name(actual), outcome=outcome,
                        note=note, recorded_by=user,
                    )
            except IntegrityError:
                # A concurrent first save won the unique (school, slot, date) race.
                current = LessonRecord.objects.select_for_update().get(school=school, slot_id=slot_id, date=day)
                if (current.outcome, current.note, current.actual_teacher_id) == (
                    outcome, note, actual.pk if actual else None
                ):
                    return Response(_row(current))
                return Response({'detail': 'The lesson changed. Reload it before saving.'}, status=409)
            old_outcome, changed, action = None, ['outcome', 'note', 'actual_teacher'], 'lesson.outcome_recorded'
        audit(request, action, target=f'lesson:{school.pk}:{slot_id}:{day}', details={
            'school_id': school.pk, 'before': old_outcome, 'after': outcome,
            'changed_fields': changed, 'revision': record.revision,
        })
        return Response(_row(record), status=201 if old_outcome is None else 200)
