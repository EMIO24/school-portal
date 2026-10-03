from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from academics.models import AcademicSession
from tenants.models import PlatformEvent

from .enrollment_periods import active_enrollment
from .models import ClassArm, SessionEnrollment, StudentProfile
from .placement_lock import lock_school, campus_is_active


class StudentTransferError(ValueError):
    """Raised when a class transfer would make enrollment history unsafe."""


@transaction.atomic
def transfer_student(
    *,
    school,
    student,
    destination_class,
    effective_date,
    actor,
    reason="",
):
    school = lock_school(school)
    locked = (
        StudentProfile.objects.select_for_update()
        .filter(pk=student.pk, school=school)
        .first()
    )
    if not locked or locked.user.school_id != school.pk:
        raise StudentTransferError("Student must belong to this school.")
    if locked.status != "active":
        raise StudentTransferError("Only an active student can be transferred.")

    destination = (
        ClassArm.objects.select_related("class_level")
        .filter(pk=destination_class.pk, school=school)
        .first()
    )
    if not destination:
        raise StudentTransferError("Destination class must belong to this school.")
    if not campus_is_active(school, destination.campus_id):
        raise StudentTransferError("Choose a destination in an active campus in this school.")

    sessions = list(
        AcademicSession.objects.filter(
            school=school,
            is_current=True,
        ).order_by("pk")[:2]
    )
    if len(sessions) != 1:
        raise StudentTransferError(
            "Set exactly one current academic session before transferring a student."
        )
    session = sessions[0]

    source = active_enrollment(
        school=school,
        student=locked,
        session=session,
        lock=True,
    )
    if not source:
        raise StudentTransferError(
            "An active current-session enrollment is required before transfer."
        )
    if locked.current_class_id != source.class_arm_id:
        raise StudentTransferError(
            "Current class does not match the active session enrollment."
        )
    if destination.pk == source.class_arm_id:
        raise StudentTransferError("Choose a different destination class.")

    if not isinstance(effective_date, date):
        raise StudentTransferError("Enter a valid transfer date.")
    if effective_date <= source.enrolled_on:
        raise StudentTransferError(
            "Transfer date must be after the current placement start date."
        )
    latest = min(timezone.localdate(), session.end_date)
    if effective_date > latest:
        raise StudentTransferError(
            "Transfer date must be within the current session and not in the future."
        )

    reason = (reason or "").strip()
    if len(reason) > 500:
        raise StudentTransferError("Reason must be 500 characters or fewer.")

    source.exited_on = effective_date - timedelta(days=1)
    source.status = "transferred"
    note = f"Transferred to {destination.full_name} effective {effective_date}."
    if reason:
        note += f" Reason: {reason}"
    source.notes = (
        source.notes + (" " if source.notes else "") + note
    )[:500]
    source.save(
        update_fields=["status", "exited_on", "notes", "updated_at"]
    )

    destination_enrollment = SessionEnrollment.objects.create(
        school=school,
        student=locked,
        session=session,
        class_arm=destination,
        status="active",
        entry_reason="transfer",
        enrolled_on=effective_date,
        notes=(
            f"Transferred from {source.class_arm.full_name}."
            + (f" Reason: {reason}" if reason else "")
        )[:500],
        created_by=actor,
    )

    locked.current_class = destination
    locked.save(update_fields=["current_class"])

    PlatformEvent.objects.create(
        actor=actor,
        actor_email=getattr(actor, "email", "") or "",
        action="school.student_transferred",
        target=str(locked.pk),
        details={
            "school_id": school.pk,
            "student_id": locked.pk,
            "session_id": session.pk,
            "source_enrollment_id": source.pk,
            "destination_enrollment_id": destination_enrollment.pk,
            "from_class_id": source.class_arm_id,
            "to_class_id": destination.pk,
            "effective_date": str(effective_date),
            "reason": reason,
        },
    )

    student.current_class_id = destination.pk
    return locked, source, destination_enrollment
