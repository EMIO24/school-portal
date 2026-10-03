from django.db import transaction

from academics.models import AcademicSession

from .enrollment_periods import active_enrollment
from .models import ClassArm, SessionEnrollment, StudentProfile
from .placement_lock import lock_school, campus_is_active


class EnrollmentPlacementError(ValueError):
    """Raised when a current-session placement would create ambiguous history."""


@transaction.atomic
def ensure_current_enrollment(
    *,
    school,
    student,
    class_arm,
    actor=None,
    entry_reason="manual",
    current_session=None,
):
    """Create or confirm a student's authoritative placement for the current session."""
    school = lock_school(school)
    if not class_arm:
        raise EnrollmentPlacementError("Choose a class before creating an enrollment.")

    locked_student = StudentProfile.objects.select_for_update().filter(
        pk=student.pk,
        school=school,
    ).first()
    if not locked_student or locked_student.user.school_id != school.pk:
        raise EnrollmentPlacementError("Student must belong to this school.")
    if locked_student.status != "active":
        raise EnrollmentPlacementError(
            "Only an active student can be assigned to a current-session class."
        )

    arm = ClassArm.objects.select_related("class_level").filter(
        pk=class_arm.pk, school=school
    ).first()
    if not arm:
        raise EnrollmentPlacementError("Class must belong to this school.")

    session = None
    if current_session is not None:
        session = AcademicSession.objects.filter(pk=current_session.pk, school=school, is_current=True).first()
    if current_session is not None and session is None:
        raise EnrollmentPlacementError(
            "The supplied academic session is not the school's current session."
        )
    if session is None:
        session = AcademicSession.objects.filter(
            school=school, is_current=True
        ).first()
    if not session:
        raise EnrollmentPlacementError(
            "Set the school's current academic session before assigning a student to a class."
        )

    enrollment = active_enrollment(
        school=school,
        student=locked_student,
        session=session,
        lock=True,
    )

    if enrollment:
        if enrollment.status != "active":
            raise EnrollmentPlacementError(
                "The student's current-session enrollment is already closed."
            )
        if enrollment.class_arm_id != arm.pk:
            raise EnrollmentPlacementError(
                "This student already has a current-session class placement. "
                "Use the class-transfer workflow to change classes safely."
            )
        if locked_student.current_class_id != arm.pk:
            locked_student.current_class = arm
            locked_student.save(update_fields=["current_class"])
        student.current_class_id = arm.pk
        return enrollment, False

    if not campus_is_active(school, arm.campus_id):
        raise EnrollmentPlacementError("Choose a class in an active campus in this school.")

    enrolled_on = min(
        max(locked_student.admission_date, session.start_date),
        session.end_date,
    )
    enrollment = SessionEnrollment.objects.create(
        school=school,
        student=locked_student,
        session=session,
        class_arm=arm,
        status="active",
        entry_reason=entry_reason,
        enrolled_on=enrolled_on,
        created_by=actor,
    )

    if locked_student.current_class_id != arm.pk:
        locked_student.current_class = arm
        locked_student.save(update_fields=["current_class"])
    student.current_class_id = arm.pk
    return enrollment, True
