from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from .models import AcademicRollover, AcademicSession, Term


class RolloverSafetyError(ValueError):
    pass


def _issue(code, message, *, count=None):
    item = {"code": code, "message": message}
    if count is not None:
        item["count"] = count
    return item


def _term_configuration_snapshot(*, school, term):
    """Return planning/configuration counts only; never historical execution records."""
    if term is None:
        return {
            "term_id": None,
            "scoring_configured": False,
            "fee_schedules": 0,
            "subject_assignments": 0,
            "timetable_entries": 0,
            "curriculum_plans": 0,
        }

    from curriculum.models import CurriculumPlan
    from enrollment.models import SubjectAssignment
    from fees.models import FeeSchedule
    from gradebook.models import TermScoring
    from timetable.models import TimetableEntry

    return {
        "term_id": term.pk,
        "scoring_configured": TermScoring.objects.filter(
            school=school, term=term
        ).exists(),
        "fee_schedules": FeeSchedule.objects.filter(
            school=school, term=term
        ).count(),
        "subject_assignments": SubjectAssignment.objects.filter(
            school=school, term=term
        ).count(),
        "timetable_entries": TimetableEntry.objects.filter(
            school=school, term=term
        ).count(),
        "curriculum_plans": CurriculumPlan.objects.filter(
            school=school, term=term
        ).count(),
    }


@transaction.atomic
def prepare_rollover_preview(*, school, source_session, destination_session, actor=None):
    """
    Build and persist a non-destructive year-end readiness preview.

    This function may update AcademicRollover preview metadata, but it never changes
    student placement, promotion decisions, current_class, session/term activation,
    financial records, attendance, results, timetable delivery, or curriculum history.
    """
    from tenants.models import School
    from enrollment.models import (
        ClassArm,
        ClassLevel,
        SessionEnrollment,
        Subject,
    )
    from promotion.models import PromotionCriteria, PromotionRecord
    from timetable.models import Period

    locked_school = School.objects.select_for_update().get(pk=school.pk)
    source = AcademicSession.objects.select_for_update().filter(
        pk=source_session.pk, school=locked_school
    ).first()
    destination = AcademicSession.objects.select_for_update().filter(
        pk=destination_session.pk, school=locked_school
    ).first()
    if not source or not destination:
        raise RolloverSafetyError(
            "Select source and destination sessions belonging to this school."
        )
    if source.pk == destination.pk:
        raise RolloverSafetyError("Source and destination sessions must differ.")
    if destination.start_date <= source.end_date:
        raise RolloverSafetyError(
            "Destination session must begin after the source session ends."
        )

    completed_rollover = AcademicRollover.objects.filter(
        school=locked_school,
        source_session=source,
        destination_session=destination,
        status="completed",
    ).order_by("-id").first()

    source_first_term = Term.objects.filter(session=source, name="first").first()
    destination_first_term = Term.objects.filter(
        session=destination, name="first"
    ).first()

    global_blockers = []
    if not source.is_current:
        global_blockers.append(_issue(
            "SOURCE_NOT_CURRENT",
            "Only the school's current academic session can be prepared for rollover.",
        ))
    if destination.is_current:
        global_blockers.append(_issue(
            "DESTINATION_ALREADY_CURRENT",
            "The destination session is already current.",
        ))
    if not destination_first_term:
        global_blockers.append(_issue(
            "DESTINATION_FIRST_TERM_MISSING",
            "Configure First Term for the destination session before rollover.",
        ))
    if completed_rollover:
        global_blockers.append(_issue(
            "ROLLOVER_ALREADY_COMPLETED",
            "This source and destination session pair has already completed rollover.",
        ))

    # A student can have several periods because of transfers. The final placement
    # is the latest recorded period in the source session and is the only placement
    # used for rollover decision validation.
    enrollment_rows = SessionEnrollment.objects.filter(
        school=locked_school,
        session=source,
    ).select_related(
        "student__user",
        "class_arm__class_level",
    ).order_by("student_id", "-enrolled_on", "-pk")

    final_enrollments = {}
    for enrollment in enrollment_rows:
        final_enrollments.setdefault(enrollment.student_id, enrollment)

    records_by_student = defaultdict(list)
    records = PromotionRecord.objects.filter(
        school=locked_school,
        from_session=source,
    ).select_related(
        "to_session",
        "from_class__class_level",
        "to_class__class_level",
    ).order_by("student_id", "id")
    for record in records:
        records_by_student[record.student_id].append(record)

    destination_enrollments = defaultdict(list)
    for enrollment in SessionEnrollment.objects.filter(
        school=locked_school,
        session=destination,
    ).select_related("class_arm__class_level").order_by("student_id", "pk"):
        destination_enrollments[enrollment.student_id].append(enrollment)

    decision_counts = {
        "promoted": 0,
        "repeated": 0,
        "graduated": 0,
        "withdrawn": 0,
    }
    unresolved_count = 0
    decided_count = 0
    lifecycle_exempt_count = 0
    student_rows = []
    issue_students = defaultdict(set)

    def add_student_issue(issues, code, message, student_id):
        issues.append({"code": code, "message": message})
        issue_students[code].add(student_id)

    for student_id, enrollment in final_enrollments.items():
        student = enrollment.student
        source_arm = enrollment.class_arm
        source_level = source_arm.class_level
        student_records = records_by_student.get(student_id, [])
        issues = []
        record = student_records[0] if len(student_records) == 1 else None

        lifecycle_exempt = (
            not student_records
            and student.status in ("withdrawn", "graduated")
            and enrollment.status == student.status
        )

        if len(student_records) > 1:
            add_student_issue(
                issues,
                "DUPLICATE_PROMOTION_DECISIONS",
                "More than one promotion decision exists for this student and source session.",
                student_id,
            )
        elif not student_records and not lifecycle_exempt:
            unresolved_count += 1
            add_student_issue(
                issues,
                "MISSING_PROMOTION_DECISION",
                "A year-end promotion, repeat, graduation, or withdrawal decision is required.",
                student_id,
            )
        elif lifecycle_exempt:
            lifecycle_exempt_count += 1
        else:
            decided_count += 1
            decision_counts[record.decision] += 1

            if record.from_class_id != source_arm.pk:
                add_student_issue(
                    issues,
                    "SOURCE_CLASS_MISMATCH",
                    "The promotion decision does not reference the student's final source-session class.",
                    student_id,
                )

            if record.decision in ("promoted", "repeated"):
                if record.to_session_id != destination.pk:
                    add_student_issue(
                        issues,
                        "DESTINATION_SESSION_MISMATCH",
                        "The promotion decision points to a different destination session.",
                        student_id,
                    )
                if not record.to_class_id:
                    add_student_issue(
                        issues,
                        "DESTINATION_CLASS_MISSING",
                        "The promotion decision requires a destination class.",
                        student_id,
                    )
                elif record.to_class.school_id != locked_school.pk:
                    add_student_issue(
                        issues,
                        "DESTINATION_CLASS_FOREIGN",
                        "The destination class does not belong to this school.",
                        student_id,
                    )
                elif record.decision == "promoted" and (
                    record.to_class.class_level.order_index
                    <= source_level.order_index
                ):
                    add_student_issue(
                        issues,
                        "PROMOTION_CLASS_NOT_HIGHER",
                        "Promoted students must move to a higher class level.",
                        student_id,
                    )
                elif record.decision == "repeated" and record.to_class_id != source_arm.pk:
                    add_student_issue(
                        issues,
                        "REPEAT_CLASS_MISMATCH",
                        "A repeat decision must retain the student's final source class.",
                        student_id,
                    )

                existing_dest = destination_enrollments.get(student_id, [])
                active_dest = [e for e in existing_dest if e.status == "active"]
                if existing_dest:
                    matching = [
                        e for e in active_dest
                        if record.to_class_id and e.class_arm_id == record.to_class_id
                    ]
                    if not matching:
                        add_student_issue(
                            issues,
                            "DESTINATION_ENROLLMENT_CONFLICT",
                            "Destination-session enrollment history already exists and does not match this decision.",
                            student_id,
                        )

            elif record.decision == "graduated" and not source_level.is_final_year:
                add_student_issue(
                    issues,
                    "GRADUATION_FROM_NONFINAL_LEVEL",
                    "Graduation is only valid from a class level marked as final year.",
                    student_id,
                )

        student_rows.append({
            "student_id": student.pk,
            "admission_number": student.admission_number,
            "student_name": student.full_name,
            "student_status": student.status,
            "source_enrollment_id": enrollment.pk,
            "source_enrollment_status": enrollment.status,
            "source_class_id": source_arm.pk,
            "source_class": source_arm.full_name,
            "source_level": source_level.name,
            "decision_id": record.pk if record else None,
            "decision": record.decision if record else None,
            "destination_session_id": record.to_session_id if record else None,
            "destination_class_id": record.to_class_id if record else None,
            "destination_class": record.to_class.full_name if record and record.to_class_id else None,
            "lifecycle_exempt": lifecycle_exempt,
            "ready": not issues,
            "issues": issues,
        })

    if not final_enrollments:
        global_blockers.append(_issue(
            "SOURCE_ENROLLMENTS_MISSING",
            "The source session has no student placement history to roll over.",
        ))

    student_blockers = []
    messages = {
        "DUPLICATE_PROMOTION_DECISIONS": "Students have duplicate year-end decisions.",
        "MISSING_PROMOTION_DECISION": "Students are still missing year-end decisions.",
        "SOURCE_CLASS_MISMATCH": "Some decisions do not match students' final source classes.",
        "DESTINATION_SESSION_MISMATCH": "Some decisions point to a different destination session.",
        "DESTINATION_CLASS_MISSING": "Some promoted or repeated students have no destination class.",
        "DESTINATION_CLASS_FOREIGN": "Some destination classes belong to another school.",
        "PROMOTION_CLASS_NOT_HIGHER": "Some promotion decisions do not move students to a higher level.",
        "REPEAT_CLASS_MISMATCH": "Some repeat decisions do not retain the source class.",
        "DESTINATION_ENROLLMENT_CONFLICT": "Some students already have conflicting destination-session enrollment history.",
        "GRADUATION_FROM_NONFINAL_LEVEL": "Some graduation decisions come from non-final class levels.",
    }
    for code, student_ids in sorted(issue_students.items()):
        student_blockers.append(_issue(
            code,
            messages[code],
            count=len(student_ids),
        ))

    source_config = _term_configuration_snapshot(
        school=locked_school, term=source_first_term
    )
    destination_config = _term_configuration_snapshot(
        school=locked_school, term=destination_first_term
    )
    class_level_count = ClassLevel.objects.filter(school=locked_school).count()
    criteria_count = PromotionCriteria.objects.filter(school=locked_school).count()
    configuration = {
        "destination_first_term": {
            "ready": destination_first_term is not None,
            "term_id": destination_first_term.pk if destination_first_term else None,
        },
        "destination_term_count": Term.objects.filter(session=destination).count(),
        "class_levels": class_level_count,
        "class_arms": ClassArm.objects.filter(school=locked_school).count(),
        "subjects": Subject.objects.filter(school=locked_school).count(),
        "periods": Period.objects.filter(school=locked_school).count(),
        "promotion_criteria": {
            "configured": criteria_count,
            "class_levels": class_level_count,
        },
        "source_first_term": source_config,
        "destination_first_term_configuration": destination_config,
    }

    warnings = []
    destination_term_count = configuration["destination_term_count"]
    if destination_term_count < 3:
        warnings.append(_issue(
            "DESTINATION_TERMS_INCOMPLETE",
            f"The destination session currently has {destination_term_count} of 3 terms configured.",
        ))
    if criteria_count < class_level_count:
        warnings.append(_issue(
            "PROMOTION_CRITERIA_INCOMPLETE",
            "Promotion criteria are not explicitly configured for every class level; default criteria may still be used.",
            count=class_level_count - criteria_count,
        ))

    comparison_fields = [
        ("scoring_configured", "DESTINATION_SCORING_NOT_PREPARED", "First-term scoring configuration has not been prepared."),
        ("fee_schedules", "DESTINATION_FEES_NOT_PREPARED", "First-term fee schedules have not been prepared."),
        ("subject_assignments", "DESTINATION_ASSIGNMENTS_NOT_PREPARED", "First-term teacher/subject assignments have not been prepared."),
        ("timetable_entries", "DESTINATION_TIMETABLE_NOT_PREPARED", "First-term timetable entries have not been prepared."),
        ("curriculum_plans", "DESTINATION_CURRICULUM_NOT_PREPARED", "First-term curriculum plans have not been prepared."),
    ]
    if destination_first_term:
        for field, code, message in comparison_fields:
            source_value = source_config[field]
            destination_value = destination_config[field]
            source_has_value = bool(source_value)
            destination_has_value = bool(destination_value)
            if source_has_value and not destination_has_value:
                warnings.append(_issue(code, message))

    blockers = global_blockers + student_blockers
    ready = not blockers

    summary = {
        "source_students": len(final_enrollments),
        "decision_required": len(final_enrollments) - lifecycle_exempt_count,
        "decided": decided_count,
        "unresolved": unresolved_count,
        "lifecycle_exempt": lifecycle_exempt_count,
        **decision_counts,
    }

    payload = {
        "source_session": {
            "id": source.pk,
            "name": source.name,
            "start_date": str(source.start_date),
            "end_date": str(source.end_date),
            "is_current": source.is_current,
        },
        "destination_session": {
            "id": destination.pk,
            "name": destination.name,
            "start_date": str(destination.start_date),
            "end_date": str(destination.end_date),
            "is_current": destination.is_current,
        },
        "ready": ready,
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "configuration": configuration,
        "students": student_rows,
        "carry_forward_policy": {
            "reuse": ["class_levels", "class_arms", "subjects", "periods"],
            "review_or_create": [
                "curriculum_plans",
                "subject_assignments",
                "timetable_entries",
                "term_scoring",
                "fee_schedules",
                "class_teachers",
            ],
            "never_copy": [
                "scores",
                "attendance_records",
                "lesson_records",
                "topic_coverage",
                "promotion_records",
                "fee_payments",
                "ledger_history",
                "invoices",
                "payment_orders",
                "cbt_attempts",
                "assignment_submissions",
                "published_communications",
            ],
        },
    }

    if completed_rollover:
        payload["rollover_id"] = completed_rollover.pk
        payload["status"] = completed_rollover.status
        return payload

    rollover = AcademicRollover.objects.select_for_update().filter(
        school=locked_school,
        source_session=source,
        destination_session=destination,
        status__in=("preparing", "ready"),
    ).order_by("-id").first()
    if not rollover:
        rollover = AcademicRollover(
            school=locked_school,
            source_session=source,
            destination_session=destination,
            created_by=actor,
        )

    rollover.status = "ready" if ready else "preparing"
    rollover.preview_snapshot = payload
    rollover.student_count = summary["source_students"]
    rollover.promoted_count = summary["promoted"]
    rollover.repeated_count = summary["repeated"]
    rollover.graduated_count = summary["graduated"]
    rollover.withdrawn_count = summary["withdrawn"]
    if rollover.created_by_id is None and actor is not None:
        rollover.created_by = actor
    rollover.save()

    payload["rollover_id"] = rollover.pk
    payload["status"] = rollover.status

    # Persist the final payload including its rollover identity/status.
    rollover.preview_snapshot = payload
    rollover.save(update_fields=["preview_snapshot", "updated_at"])
    return payload


@transaction.atomic
def execute_rollover(*, school, source_session, destination_session, actor, idempotency_key=""):
    """
    Atomically finalize one academic-year cutover.

    The executor refreshes readiness inside the same transaction, locks the school,
    rollover, student placements and student accounts, then applies only the
    placement/lifecycle changes implied by already-recorded PromotionRecord rows.
    Replays for an already-completed session pair are safe and return the original
    completion summary.
    """
    from enrollment.models import SessionEnrollment, StudentProfile
    from promotion.models import PromotionRecord
    from tenants.models import PlatformEvent, School

    locked_school = School.objects.select_for_update().get(pk=school.pk)
    source = AcademicSession.objects.select_for_update().filter(
        pk=source_session.pk, school=locked_school
    ).first()
    destination = AcademicSession.objects.select_for_update().filter(
        pk=destination_session.pk, school=locked_school
    ).first()
    if not source or not destination:
        raise RolloverSafetyError(
            "Select source and destination sessions belonging to this school."
        )

    completed = AcademicRollover.objects.select_for_update().filter(
        school=locked_school,
        source_session=source,
        destination_session=destination,
        status="completed",
    ).order_by("-id").first()
    if completed:
        return {
            "rollover_id": completed.pk,
            "status": completed.status,
            "completed_at": completed.completed_at.isoformat() if completed.completed_at else None,
            "idempotent_replay": True,
            "summary": {
                "source_students": completed.student_count,
                "promoted": completed.promoted_count,
                "repeated": completed.repeated_count,
                "graduated": completed.graduated_count,
                "withdrawn": completed.withdrawn_count,
            },
        }

    if idempotency_key:
        existing_key = AcademicRollover.objects.select_for_update().filter(
            school=locked_school,
            idempotency_key=idempotency_key,
        ).first()
        if existing_key and (
            existing_key.source_session_id != source.pk
            or existing_key.destination_session_id != destination.pk
        ):
            raise RolloverSafetyError(
                "This rollover idempotency key has already been used for another session pair."
            )

    preview = prepare_rollover_preview(
        school=locked_school,
        source_session=source,
        destination_session=destination,
        actor=actor,
    )
    if not preview.get("ready"):
        first = (preview.get("blockers") or [{}])[0].get(
            "message", "The academic rollover is not ready."
        )
        raise RolloverSafetyError(first)

    rollover = AcademicRollover.objects.select_for_update().get(
        pk=preview["rollover_id"],
        school=locked_school,
        source_session=source,
        destination_session=destination,
    )
    if rollover.status != "ready":
        raise RolloverSafetyError(
            "Refresh the rollover preview before executing the academic rollover."
        )
    if idempotency_key:
        rollover.idempotency_key = idempotency_key
        rollover.save(update_fields=["idempotency_key", "updated_at"])

    first_term = Term.objects.select_for_update().filter(
        session=destination, name="first"
    ).first()
    if not first_term:
        raise RolloverSafetyError(
            "Configure First Term for the destination session before rollover."
        )

    # Lock all relevant records again after the fresh preview so no concurrent
    # placement/decision mutation can slip between readiness and execution.
    enrollment_rows = list(
        SessionEnrollment.objects.select_for_update().filter(
            school=locked_school,
            session=source,
        ).select_related("class_arm__class_level").order_by(
            "student_id", "-enrolled_on", "-pk"
        )
    )
    final_enrollments = {}
    for enrollment in enrollment_rows:
        final_enrollments.setdefault(enrollment.student_id, enrollment)

    # Lock PromotionRecord rows themselves. Nullable to_session/to_class relations
    # must not be joined into SELECT ... FOR UPDATE on PostgreSQL because they
    # become the nullable side of LEFT OUTER JOINs.
    records = list(
        PromotionRecord.objects.select_for_update(of=("self",)).filter(
            school=locked_school,
            from_session=source,
        ).order_by("student_id", "id")
    )
    records = list(
        PromotionRecord.objects.filter(pk__in=[record.pk for record in records])
        .select_related(
            "to_session",
            "from_class__class_level",
            "to_class__class_level",
        )
        .order_by("student_id", "id")
    )
    records_by_student = defaultdict(list)
    for record in records:
        records_by_student[record.student_id].append(record)

    destination_rows = list(
        SessionEnrollment.objects.select_for_update().filter(
            school=locked_school,
            session=destination,
        ).select_related("class_arm").order_by("student_id", "pk")
    )
    destination_by_student = defaultdict(list)
    for enrollment in destination_rows:
        destination_by_student[enrollment.student_id].append(enrollment)

    student_ids = list(final_enrollments)
    students = {
        student.pk: student
        for student in StudentProfile.objects.select_for_update().select_related(
            "user"
        ).filter(school=locked_school, pk__in=student_ids)
    }

    counts = {
        "promoted": 0,
        "repeated": 0,
        "graduated": 0,
        "withdrawn": 0,
    }

    for student_id, source_enrollment in final_enrollments.items():
        student = students.get(student_id)
        if student is None:
            raise RolloverSafetyError(
                "A source-session enrollment references a missing student."
            )

        student_records = records_by_student.get(student_id, [])
        lifecycle_exempt = (
            not student_records
            and student.status in ("withdrawn", "graduated")
            and source_enrollment.status == student.status
        )
        if lifecycle_exempt:
            continue
        if len(student_records) != 1:
            raise RolloverSafetyError(
                "Every rollover student must have exactly one year-end decision."
            )

        record = student_records[0]
        decision = record.decision
        if record.from_class_id != source_enrollment.class_arm_id:
            raise RolloverSafetyError(
                "A promotion decision no longer matches the student's final source class."
            )

        if decision in ("promoted", "repeated"):
            if record.to_session_id != destination.pk or not record.to_class_id:
                raise RolloverSafetyError(
                    "A promoted or repeated student has an invalid destination placement."
                )

            if source_enrollment.status == "active":
                source_enrollment.status = "completed"
                source_enrollment.exited_on = source.end_date
                source_enrollment.notes = (
                    source_enrollment.notes
                    + (" " if source_enrollment.notes else "")
                    + f"Closed by academic rollover {rollover.pk}: {decision}."
                )[:500]
                source_enrollment.save(
                    update_fields=["status", "exited_on", "notes", "updated_at"]
                )
            elif not (
                source_enrollment.status == "completed"
                and source_enrollment.exited_on == source.end_date
            ):
                raise RolloverSafetyError(
                    "A source placement changed after rollover preview."
                )

            existing_destination = destination_by_student.get(student_id, [])
            active_destination = [
                row for row in existing_destination if row.status == "active"
            ]
            if existing_destination:
                if len(active_destination) != 1 or active_destination[0].class_arm_id != record.to_class_id:
                    raise RolloverSafetyError(
                        "Destination enrollment history changed after rollover preview."
                    )
                destination_enrollment = active_destination[0]
            else:
                destination_enrollment = SessionEnrollment.objects.create(
                    school=locked_school,
                    student=student,
                    session=destination,
                    class_arm=record.to_class,
                    status="active",
                    entry_reason="promotion" if decision == "promoted" else "repeat",
                    enrolled_on=destination.start_date,
                    notes=f"Created by academic rollover {rollover.pk} from promotion decision {record.pk}.",
                    created_by=actor,
                )
                destination_by_student[student_id].append(destination_enrollment)

            if student.current_class_id not in (
                source_enrollment.class_arm_id,
                record.to_class_id,
            ):
                raise RolloverSafetyError(
                    "The student's current class changed after rollover preview."
                )
            student.current_class = record.to_class
            student.status = "active"
            student.user.is_active = True
            student.user.save(update_fields=["is_active"])
            student.save(update_fields=["current_class", "status"])
            counts[decision] += 1

        elif decision in ("graduated", "withdrawn"):
            if destination_by_student.get(student_id):
                raise RolloverSafetyError(
                    "Graduated or withdrawn students cannot have destination-session enrollment history."
                )

            if source_enrollment.status == "active":
                source_enrollment.status = decision
                source_enrollment.exited_on = source.end_date
                source_enrollment.notes = (
                    source_enrollment.notes
                    + (" " if source_enrollment.notes else "")
                    + f"Closed by academic rollover {rollover.pk}: {decision}."
                )[:500]
                source_enrollment.save(
                    update_fields=["status", "exited_on", "notes", "updated_at"]
                )
            elif not (
                source_enrollment.status == decision
                and source_enrollment.exited_on is not None
            ):
                raise RolloverSafetyError(
                    "A source placement changed after rollover preview."
                )

            if student.current_class_id not in (
                None,
                source_enrollment.class_arm_id,
            ):
                raise RolloverSafetyError(
                    "The student's current class changed after rollover preview."
                )
            student.current_class = None
            student.status = decision
            student.user.is_active = False
            student.user.save(update_fields=["is_active"])
            student.save(update_fields=["current_class", "status"])
            counts[decision] += 1
        else:
            raise RolloverSafetyError("A promotion decision is not valid for rollover.")

    # No active source placements may survive the cutover.
    if SessionEnrollment.objects.filter(
        school=locked_school,
        session=source,
        status="active",
    ).exists():
        raise RolloverSafetyError(
            "Active source-session placements remain after applying rollover decisions."
        )

    AcademicSession.objects.filter(
        school=locked_school, is_current=True
    ).exclude(pk=destination.pk).update(is_current=False)
    if not destination.is_current:
        AcademicSession.objects.filter(pk=destination.pk).update(is_current=True)
        destination.is_current = True

    Term.objects.filter(
        session__school=locked_school, is_current=True
    ).exclude(pk=first_term.pk).update(is_current=False)
    if not first_term.is_current:
        Term.objects.filter(pk=first_term.pk).update(is_current=True)
        first_term.is_current = True

    completed_at = timezone.now()
    rollover.status = "completed"
    rollover.completed_by = actor
    rollover.completed_at = completed_at
    rollover.student_count = len(final_enrollments)
    rollover.promoted_count = counts["promoted"]
    rollover.repeated_count = counts["repeated"]
    rollover.graduated_count = counts["graduated"]
    rollover.withdrawn_count = counts["withdrawn"]
    rollover.preview_snapshot = {
        **preview,
        "status": "completed",
        "completed_at": completed_at.isoformat(),
        "execution_summary": {
            "source_students": len(final_enrollments),
            **counts,
        },
    }
    rollover.save()

    PlatformEvent.objects.create(
        actor=actor,
        actor_email=actor.email if actor else "",
        action="school.academic_rollover",
        target=str(rollover.pk),
        details={
            "school_id": locked_school.pk,
            "rollover_id": rollover.pk,
            "source_session_id": source.pk,
            "destination_session_id": destination.pk,
            "source_students": len(final_enrollments),
            **counts,
        },
    )

    return {
        "rollover_id": rollover.pk,
        "status": rollover.status,
        "completed_at": completed_at.isoformat(),
        "idempotent_replay": False,
        "source_session_id": source.pk,
        "destination_session_id": destination.pk,
        "current_term_id": first_term.pk,
        "summary": {
            "source_students": len(final_enrollments),
            **counts,
        },
    }


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

    first_term = Term.objects.select_for_update().filter(
        session=target, name="first"
    ).first()
    if not first_term:
        raise RolloverSafetyError(
            "Configure First Term for the destination session before activating it."
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
    Term.objects.filter(
        session__school=locked_school, is_current=True
    ).exclude(pk=first_term.pk).update(is_current=False)
    if not first_term.is_current:
        first_term.is_current = True
        first_term.save(update_fields=["is_current"])
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
    if current_session and current_session.pk != term.session_id and term.name != "first":
        raise RolloverSafetyError(
            "A new academic session must begin with First Term."
        )
    if not current_session or current_session.pk != term.session_id:
        activate_session(school=locked_school, target_session=term.session)

    Term.objects.filter(
        session__school=locked_school, is_current=True
    ).exclude(pk=term.pk).update(is_current=False)
    term.is_current = True
    term.save(update_fields=["is_current"])
    return term
