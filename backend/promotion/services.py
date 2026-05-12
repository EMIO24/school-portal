from decimal import Decimal
from django.db.models import Avg, Count, Q


def evaluate_student(student, session, criteria):
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

    # Attendance % for session
    attend = AttendanceRecord.objects.filter(
        student=student.user,
        attendance_session__term__in=terms,
        attendance_session__school=student.school,
    ).aggregate(
        present=Count('id', filter=Q(status='present')),
        total=Count('id'),
    )
    attend_pct = int(attend['present'] / attend['total'] * 100) if attend['total'] else 0

    criteria_met = (
        subjects_passed >= criteria.min_subjects_to_pass
        and float(session_avg) >= float(criteria.min_average_score)
        and attend_pct >= criteria.min_attendance_pct
    )

    # Final-year students graduate rather than promote (configurable via ClassLevel.is_final_year)
    is_final = student.current_class and student.current_class.class_level.is_final_year
    recommended = 'graduated' if is_final else ('promoted' if criteria_met else 'repeated')

    return {
        'student_id':    student.id,
        'student_name':  student.user.get_full_name(),
        'class':         student.current_class.full_name if student.current_class else '',
        'session_avg':   round(float(session_avg), 1),
        'subjects_passed': subjects_passed,
        'attendance_pct':  attend_pct,
        'criteria_met':    criteria_met,
        'recommended':     recommended,
    }
