from celery import shared_task
from django.db.models import Avg, Count, Q, Sum
from decimal import Decimal


@shared_task
def compute_school_analytics(school_id, term_id):
    from tenants.models import School
    from academics.models import Term
    from enrollment.models import StudentProfile, ClassArm
    from gradebook.models import ScoreEntry, GradeScale
    from attendance.models import AttendanceRecord
    from fees.models import FeeSchedule, FeePayment
    from results.models import ResultRemark
    from .models import AnalyticsSnapshot

    import logging
    logger = logging.getLogger(__name__)

    try:
        school = School.objects.get(pk=school_id)
        term   = Term.objects.get(pk=term_id)
    except Exception:
        logger.exception("compute_school_analytics(%s, %s) failed — school or term not found", school_id, term_id)
        raise

    scores = ScoreEntry.objects.filter(school=school, term=term)

    total_students  = StudentProfile.objects.filter(school=school, status='active').count()
    total_teachers  = school.staff.filter(employment_status='active').count()
    total_subjects  = scores.values('subject').distinct().count()
    school_average  = scores.aggregate(a=Avg('total_score'))['a'] or 0
    pass_count      = scores.filter(total_score__gte=50).values('student').distinct().count()
    student_count   = scores.values('student').distinct().count()
    overall_pass_rate = round(pass_count / student_count * 100, 1) if student_count else 0

    # Subject averages
    subject_avgs = []
    for row in scores.values('subject__name').annotate(avg=Avg('total_score'), total=Count('id'), passed=Count('id', filter=Q(total_score__gte=50))).order_by('avg'):
        subject_avgs.append({
            'subject':   row['subject__name'],
            'avg':       round(float(row['avg']), 1),
            'pass_rate': round(row['passed'] / row['total'] * 100, 1) if row['total'] else 0,
        })

    # Class arm averages
    class_avgs = []
    for arm in ClassArm.objects.filter(school=school):
        arm_scores = scores.filter(student__student_profile__current_class=arm)
        avg = arm_scores.aggregate(a=Avg('total_score'))['a']
        if avg:
            class_avgs.append({'class_arm': arm.full_name, 'avg': round(float(avg), 1)})

    # Grade distribution (Nigerian scale)
    grade_dist = {}
    for entry in scores.values('total_score'):
        ts = float(entry['total_score'])
        if ts >= 70:   g = 'A1'
        elif ts >= 65: g = 'B2'
        elif ts >= 60: g = 'B3'
        elif ts >= 55: g = 'C4'
        elif ts >= 50: g = 'C5'
        elif ts >= 45: g = 'C6'
        elif ts >= 40: g = 'D7'
        elif ts >= 30: g = 'E8'
        else:          g = 'F9'
        grade_dist[g] = grade_dist.get(g, 0) + 1

    # Attendance school avg
    attend_pct = 0
    from django.db.models import F
    attend_data = (
        AttendanceRecord.objects
        .filter(attendance_session__term=term, school=school)
        .aggregate(
            present=Count('id', filter=Q(status='present')),
            total=Count('id'),
        )
    )
    if attend_data['total']:
        attend_pct = round(attend_data['present'] / attend_data['total'] * 100, 1)

    # Fee collection rate
    fee_expected = FeeSchedule.objects.filter(school=school, term=term).aggregate(t=Sum('amount'))['t'] or Decimal('0')
    fee_paid     = FeePayment.objects.filter(school=school, fee_schedule__term=term).aggregate(t=Sum('amount_paid'))['t'] or Decimal('0')
    fee_rate     = round(float(fee_paid) / float(fee_expected) * 100, 1) if fee_expected else 0

    # Top 10 students  (ResultRemark.student is FK to CustomUser)
    top_students = []
    for remark in (
        ResultRemark.objects
        .filter(school=school, term=term)
        .select_related('student', 'student__student_profile__current_class')
        .order_by('computed_position')[:10]
    ):
        s_scores = scores.filter(student=remark.student)
        avg = s_scores.aggregate(a=Avg('total_score'))['a']
        profile   = getattr(remark.student, 'student_profile', None)
        class_arm = profile.current_class if profile else None
        top_students.append({
            'name':     remark.student.get_full_name(),
            'class':    class_arm.full_name if class_arm else '',
            'average':  round(float(avg), 1) if avg else 0,
            'position': remark.computed_position,
        })

    data = {
        'total_students':     total_students,
        'total_teachers':     total_teachers,
        'total_subjects':     total_subjects,
        'school_average':     round(float(school_average), 1),
        'overall_pass_rate':  overall_pass_rate,
        'subject_averages':   subject_avgs,
        'class_averages':     class_avgs,
        'grade_distribution': grade_dist,
        'attendance_school_avg': attend_pct,
        'fee_collection_rate':   fee_rate,
        'top_students':       top_students,
    }

    AnalyticsSnapshot.objects.update_or_create(
        school=school, term=term,
        defaults={'data': data},
    )


@shared_task
def compute_all_schools_analytics():
    from academics.models import Term
    for term in Term.objects.filter(is_current=True).select_related('session__school'):
        compute_school_analytics.delay(term.session.school_id, term.id)
