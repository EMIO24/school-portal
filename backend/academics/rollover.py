from django.db import transaction

from .models import AcademicRollover, AcademicSession, Term


class RolloverSafetyError(ValueError):
    pass


@transaction.atomic
def activate_session(*, school, target_session):
    """Safely change the school's current session outside the future rollover executor."""
    from tenants.models import School
    from enrollment.models import SessionEnrollment

    locked_school = School.objects.select_for_update().get(pk=school.pk)
    target = AcademicSession.objects.select_for_update().filter(
        pk=target_session.pk, school=locked_school
    ).first()
    if not target:
        raise RolloverSafetyError("Select an academic session belonging to this school.")

    current = AcademicSession.objects.select_for_update().filter(
        school=locked_school, is_current=True
    ).exclude(pk=target.pk).first()
    if not current:
        if not target.is_current:
            target.is_current = True
            target.save(update_fields=["is_current"])
        return target

    if target.start_date <= current.end_date:
        raise RolloverSafetyError(
            "A replacement current session must begin after the current session ends."
        )

    active_source = SessionEnrollment.objects.filter(
        school=locked_school, session=current, status="active"
    ).exists()
    completed_rollover = AcademicRollover.objects.filter(
        school=locked_school,
        source_session=current,
        destination_session=target,
        status="completed",
    ).exists()
    if active_source and not completed_rollover:
        raise RolloverSafetyError(
            "The current session still has active student placements. Complete the academic rollover before activating the next session."
        )

    AcademicSession.objects.filter(
        school=locked_school, is_current=True
    ).exclude(pk=target.pk).update(is_current=False)
    target.is_current = True
    target.save(update_fields=["is_current"])
    return target


@transaction.atomic
def activate_term(*, school, target_term):
    """Activate a term without allowing it to bypass cross-session rollover safety."""
    from tenants.models import School

    locked_school = School.objects.select_for_update().get(pk=school.pk)
    term = Term.objects.select_for_update().select_related("session").filter(
        pk=target_term.pk, session__school=locked_school
    ).first()
    if not term:
        raise RolloverSafetyError("Select a term belonging to this school.")

    current_session = AcademicSession.objects.select_for_update().filter(
        school=locked_school, is_current=True
    ).first()
    if not current_session or current_session.pk != term.session_id:
        activate_session(school=locked_school, target_session=term.session)

    Term.objects.filter(
        session__school=locked_school, is_current=True
    ).exclude(pk=term.pk).update(is_current=False)
    term.is_current = True
    term.save(update_fields=["is_current"])
    return term
