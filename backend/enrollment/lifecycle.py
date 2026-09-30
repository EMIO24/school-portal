from datetime import date

from django.db import transaction
from django.utils import timezone

from academics.models import AcademicSession
from tenants.models import PlatformEvent

from .enrollment_periods import active_enrollment
from .models import StudentProfile


class StudentLifecycleError(ValueError):
    """Raised when a requested student lifecycle transition is not valid."""


@transaction.atomic
def transition_student(
    *,
    school,
    student,
    action,
    actor,
    effective_date=None,
    reason="",
):
    if action not in {"suspend", "reactivate", "withdraw"}:
        raise StudentLifecycleError("Select a valid student lifecycle action.")

    locked = (
        StudentProfile.objects.select_for_update()
        .select_related("user")
        .filter(pk=student.pk, school=school)
        .first()
    )
    if not locked or locked.user.school_id != school.pk:
        raise StudentLifecycleError("Student must belong to this school.")

    reason = (reason or "").strip()
    if len(reason) > 500:
        raise StudentLifecycleError("Reason must be 500 characters or fewer.")

    current_session = AcademicSession.objects.filter(
        school=school,
        is_current=True,
    ).first()
    enrollment = None
    if current_session:
        enrollment = active_enrollment(
            school=school,
            student=locked,
            session=current_session,
            lock=True,
        )

    previous_status = locked.status

    if action == "suspend":
        if locked.status != "active":
            raise StudentLifecycleError("Only an active student can be suspended.")
        if not enrollment or enrollment.status != "active":
            raise StudentLifecycleError(
                "An active current-session enrollment is required before suspension."
            )
        if locked.current_class_id != enrollment.class_arm_id:
            raise StudentLifecycleError(
                "Current class does not match the active session enrollment."
            )

        locked.status = "suspended"
        locked.user.is_active = False
        locked.user.save(update_fields=["is_active"])
        locked.save(update_fields=["status"])

    elif action == "reactivate":
        if locked.status != "suspended":
            raise StudentLifecycleError(
                "Only a suspended student can be reactivated."
            )
        if not enrollment or enrollment.status != "active":
            raise StudentLifecycleError(
                "An active current-session enrollment is required before reactivation."
            )
        if locked.current_class_id != enrollment.class_arm_id:
            raise StudentLifecycleError(
                "Current class does not match the active session enrollment."
            )

        locked.status = "active"
        locked.user.is_active = True
        locked.user.save(update_fields=["is_active"])
        locked.save(update_fields=["status"])

    else:
        if locked.status not in {"active", "suspended"}:
            raise StudentLifecycleError(
                "Only an active or suspended student can be withdrawn."
            )
        if not enrollment or enrollment.status != "active":
            raise StudentLifecycleError(
                "An active current-session enrollment is required before withdrawal."
            )

        effective = effective_date or timezone.localdate()
        if not isinstance(effective, date):
            raise StudentLifecycleError("Enter a valid withdrawal date.")
        latest = min(timezone.localdate(), current_session.end_date)
        if effective < enrollment.enrolled_on or effective > latest:
            raise StudentLifecycleError(
                "Withdrawal date must be within the enrollment period and not in the future."
            )

        enrollment.status = "withdrawn"
        enrollment.exited_on = effective
        note = f"Withdrawn by lifecycle action."
        if reason:
            note += f" Reason: {reason}"
        enrollment.notes = (
            enrollment.notes
            + (" " if enrollment.notes else "")
            + note
        )[:500]
        enrollment.save(
            update_fields=["status", "exited_on", "notes", "updated_at"]
        )

        locked.status = "withdrawn"
        locked.current_class = None
        locked.user.is_active = False
        locked.user.save(update_fields=["is_active"])
        locked.save(update_fields=["status", "current_class"])

    PlatformEvent.objects.create(
        actor=actor,
        actor_email=getattr(actor, "email", "") or "",
        action={
            "suspend": "school.student_suspended",
            "reactivate": "school.student_reactivated",
            "withdraw": "school.student_withdrawn",
        }[action],
        target=str(locked.pk),
        details={
            "school_id": school.pk,
            "student_id": locked.pk,
            "enrollment_id": enrollment.pk if enrollment else None,
            "previous_status": previous_status,
            "new_status": locked.status,
            "effective_date": (
                str(enrollment.exited_on)
                if action == "withdraw" and enrollment
                else None
            ),
            "reason": reason,
        },
    )

    student.status = locked.status
    student.current_class_id = locked.current_class_id
    student.user.is_active = locked.user.is_active
    return locked
