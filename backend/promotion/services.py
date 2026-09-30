from decimal import Decimal
from django.db.models import Avg, Count, Q


def evaluate_student(student, session, criteria, class_arm=None):
    from gradebook.models import ScoreEntry
    from attendance.models import AttendanceRecord
    from academics.models import Term

    terms = Term.objects.filter(session=session)

    # Session average across all terms
    scores = ScoreEntry.objects.filter(
        student=student.user,
        session=session,
        school=student.school,
    )
    session_avg = scores.aggregate(a=Avg('total_score'))['a'] or Decimal('0')

    # Subjects passed (avg across all terms >= 50)
    subjects_passed = 0
    for subj_id in scores.values_list('subject', flat=True).distinct():
        subj_avg = scores.filter(subject_id=subj_id).aggregate(a=Avg('total_score'))['a'] or Decimal('0')
        if subj_avg >= 50:
            subjects_passed += 1

    # Attendance % for session. Match attendance reports: late counts as present
    # and excused absences do not reduce the percentage.
    attend = AttendanceRecord.objects.filter(
        student=student.user,
        attendance_session__term__in=terms,
        attendance_session__school=student.school,
    ).aggregate(
        present=Count('id', filter=Q(status='present')),
        late=Count('id', filter=Q(status='late')),
        excused=Count('id', filter=Q(status='excused')),
        total=Count('id'),
    )
    counted_total = max((attend['total'] or 0) - (attend['excused'] or 0), 0)
    effective_present = (attend['present'] or 0) + (attend['late'] or 0)
    attend_pct = round(effective_present / counted_total * 100, 1) if counted_total else 0

    criteria_met = (
        subjects_passed >= criteria.min_subjects_to_pass
        and float(session_avg) >= float(criteria.min_average_score)
        and attend_pct >= criteria.min_attendance_pct
    )

    # Historical class context is authoritative when the caller supplies it.
    source_class = class_arm or student.current_class
    is_final = bool(
        source_class and source_class.class_level.is_final_year
    )
    recommended = (
        'graduated'
        if is_final
        else ('promoted' if criteria_met else 'repeated')
    )

    return {
        'student_id': student.id,
        'student_name': student.user.get_full_name(),
        'class': source_class.full_name if source_class else '',
        'class_arm_id': source_class.id if source_class else None,
        'class_level_id': source_class.class_level_id if source_class else None,
        'session_avg': round(float(session_avg), 1),
        'subjects_passed': subjects_passed,
        'attendance_pct': attend_pct,
        'criteria_met': criteria_met,
        'recommended': recommended,
    }
