from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import SessionEnrollment


class EnrollmentResolutionError(ValueError):
    """Raised when enrollment-period history cannot be resolved safely."""


def active_enrollment(*, school, student, session, lock=False):
    qs = SessionEnrollment.objects.filter(
        school=school,
        student=student,
        session=session,
        status="active",
    )
    if lock:
        qs = qs.select_for_update()
    rows = list(qs.order_by("enrolled_on", "pk")[:2])
    if len(rows) > 1:
        raise EnrollmentResolutionError(
            "Multiple active enrollments exist for this student and session."
        )
    return rows[0] if rows else None


def enrollment_on_date(*, school, student, session, on_date):
    rows = list(
        SessionEnrollment.objects.filter(
            school=school,
            student=student,
            session=session,
            enrolled_on__lte=on_date,
        )
        .filter(Q(exited_on__isnull=True) | Q(exited_on__gte=on_date))
        .select_related("class_arm", "class_arm__class_level")
        .order_by("enrolled_on", "pk")[:2]
    )
    if len(rows) > 1:
        raise EnrollmentResolutionError(
            "Overlapping enrollment periods make class membership ambiguous."
        )
    return rows[0] if rows else None


def enrollment_for_term(*, school, student, term):
    rows = list(
        SessionEnrollment.objects.filter(
            school=school,
            student=student,
            session=term.session,
            enrolled_on__lte=term.end_date,
        )
        .filter(Q(exited_on__isnull=True) | Q(exited_on__gte=term.start_date))
        .select_related("class_arm", "class_arm__class_level")
        .order_by("enrolled_on", "pk")
    )
    if len(rows) > 1:
        raise EnrollmentResolutionError(
            "Student changed class during this term; use record-specific class history."
        )
    return rows[0] if rows else None


def terminal_enrollment(*, school, student, session, lock=False):
    qs = SessionEnrollment.objects.filter(
        school=school,
        student=student,
        session=session,
    )
    if lock:
        qs = qs.select_for_update()
    rows = list(qs.order_by("-enrolled_on", "-pk")[:2])
    if not rows:
        return None
    latest = rows[0]
    if len(rows) > 1:
        previous = rows[1]
        if previous.exited_on is None or previous.exited_on >= latest.enrolled_on:
            raise EnrollmentResolutionError(
                "Overlapping enrollment periods make final placement ambiguous."
            )
    return latest


def enrolled_user_ids_for_class_on_date(*, school, class_arm, session, on_date):
    return SessionEnrollment.objects.filter(
        school=school,
        class_arm=class_arm,
        session=session,
        enrolled_on__lte=on_date,
    ).filter(
        Q(exited_on__isnull=True) | Q(exited_on__gte=on_date)
    ).values_list("student__user_id", flat=True)
