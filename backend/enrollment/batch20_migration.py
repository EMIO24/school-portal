"""Batch 20 historical migration and reconciliation helpers.

Historical imports are evidence reconstruction only:
- never activate an old session/term;
- never rewrite StudentProfile.current_class for past placements;
- never create payment orders, Paystack events or receipts;
- conflicts are REVIEW outcomes, not implicit overwrites.
"""
from decimal import Decimal
import hashlib

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import models, transaction

from academics.models import AcademicSession, Term
from attendance.models import AttendanceRecord, AttendanceSession
from gradebook.models import ScoreEntry
from fees.ledger import post_adjustment
from fees.models import StudentFinanceAccount, StudentLedgerEntry
from .models import (
    ClassArm,
    MigrationConflict,
    MigrationStudentReference,
    SessionEnrollment,
    StudentProfile,
    Subject,
)


BATCH20_DOMAINS = {
    "historical_sessions": (
        ("session", "start_date", "end_date"),
        ("session", "start_date", "end_date"),
    ),
    "historical_terms": (
        ("session", "term", "start_date", "end_date"),
        ("session", "term", "start_date", "end_date", "next_term_begins"),
    ),
    "historical_enrollments": (
        ("student_ref", "session", "class_level", "class_arm", "enrolled_on", "status"),
        ("student_ref", "session", "class_level", "class_arm", "enrolled_on", "exited_on", "status", "entry_reason"),
    ),
    "historical_results": (
        ("student_ref", "session", "term", "subject_code", "class_level", "class_arm",
         "first_test", "second_test", "assignment", "project", "practical", "exam_score"),
        ("student_ref", "session", "term", "subject_code", "class_level", "class_arm",
         "first_test", "second_test", "assignment", "project", "practical", "exam_score", "is_published"),
    ),
    "historical_attendance": (
        ("student_ref", "session", "term", "class_level", "class_arm", "date", "status"),
        ("student_ref", "session", "term", "class_level", "class_arm", "date", "status", "remark"),
    ),
    "historical_finance": (
        ("student_ref", "effective_date", "description", "reference"),
        ("student_ref", "effective_date", "description", "debit", "credit", "reference", "session", "term"),
    ),
}


class MigrationReview(Exception):
    def __init__(self, field, reason, *, conflict_type="historical_conflict", candidates=None):
        self.field = field
        self.reason = reason
        self.conflict_type = conflict_type
        self.candidates = candidates or []
        super().__init__(reason)


def _date(value, field):
    from .migration_import import date as parse_date
    return parse_date(value, field)


def _student_for(school, reference):
    identity = MigrationStudentReference.objects.filter(
        school=school, reference__iexact=reference
    ).select_related("student__user").first()
    student = identity.student if identity else StudentProfile.objects.filter(
        school=school, admission_number__iexact=reference
    ).select_related("user").first()
    if not student or student.user.school_id != school.pk:
        raise ValueError("student_ref", "Match one student in this school by source reference or admission number.")
    return student


def _session_for(school, name):
    session = AcademicSession.objects.filter(school=school, name__iexact=name.strip()).first()
    if not session:
        raise ValueError("session", "Import this historical academic session first.")
    return session


def _term_for(session, name):
    value = name.strip().casefold()
    aliases = {"1": "first", "1st": "first", "first term": "first",
               "2": "second", "2nd": "second", "second term": "second",
               "3": "third", "3rd": "third", "third term": "third"}
    value = aliases.get(value, value)
    if value not in ("first", "second", "third"):
        raise ValueError("term", "Use first, second or third.")
    term = Term.objects.filter(session=session, name=value).first()
    if not term:
        raise ValueError("term", "Import this historical term first.")
    return term


def _arm_for(school, level_name, arm_name):
    from .migration_import import arm_for, level_for
    _, level = level_for(school, level_name)
    return arm_for(school, level, arm_name)


def _decimal_score(row, field):
    try:
        value = Decimal(str(row[field]))
    except Exception:
        raise ValueError(field, "Enter a numeric score.")
    if not value.is_finite() or value < 0 or value > 100:
        raise ValueError(field, "Enter a score between 0 and 100.")
    return value.quantize(Decimal("0.01"))


def _placement_for(student, session, arm, on_date=None):
    qs = SessionEnrollment.objects.filter(
        school=student.school, student=student, session=session, class_arm=arm
    )
    if on_date:
        qs = qs.filter(enrolled_on__lte=on_date).filter(
            models.Q(exited_on__isnull=True) | models.Q(exited_on__gte=on_date)
        )
    placement = qs.order_by("-enrolled_on", "-pk").first()
    if not placement:
        raise ValueError(
            "class_arm",
            "Historical placement does not support this record. Import student placement history first.",
        )
    return placement


def assess_batch20(domain, row, school):
    if domain == "historical_sessions":
        start = _date(row["start_date"], "start_date")
        end = _date(row["end_date"], "end_date")
        if not start or not end or start >= end:
            raise ValueError("end_date", "Academic session end date must be after its start date.")
        existing = AcademicSession.objects.filter(school=school, name__iexact=row["session"].strip()).first()
        if existing:
            if existing.start_date == start and existing.end_date == end:
                return "REUSE", {}
            raise MigrationReview(
                "session",
                "This session name already exists with different dates.",
                conflict_type="session_dates",
                candidates=[{"id": existing.pk, "name": existing.name,
                             "start_date": str(existing.start_date), "end_date": str(existing.end_date)}],
            )
        overlap = AcademicSession.objects.filter(
            school=school, start_date__lte=end, end_date__gte=start
        ).first()
        if overlap:
            raise MigrationReview(
                "start_date",
                "These dates overlap another academic session.",
                conflict_type="session_overlap",
                candidates=[{"id": overlap.pk, "name": overlap.name}],
            )
        return "CREATE", {"name": row["session"].strip(), "start": start, "end": end}

    if domain == "historical_terms":
        session = _session_for(school, row["session"])
        term_name = row["term"].strip().casefold()
        aliases = {"1": "first", "1st": "first", "first term": "first",
                   "2": "second", "2nd": "second", "second term": "second",
                   "3": "third", "3rd": "third", "third term": "third"}
        term_name = aliases.get(term_name, term_name)
        if term_name not in ("first", "second", "third"):
            raise ValueError("term", "Use first, second or third.")
        start = _date(row["start_date"], "start_date")
        end = _date(row["end_date"], "end_date")
        next_begins = _date(row.get("next_term_begins", ""), "next_term_begins")
        if not start or not end or start >= end or start < session.start_date or end > session.end_date:
            raise ValueError("start_date", "Term dates must fall within the selected session.")
        existing = Term.objects.filter(session=session, name=term_name).first()
        if existing:
            if (existing.start_date, existing.end_date, existing.next_term_begins) == (start, end, next_begins):
                return "REUSE", {}
            raise MigrationReview("term", "This term already exists with different dates.", conflict_type="term_dates",
                                  candidates=[{"id": existing.pk, "name": existing.name}])
        return "CREATE", {"session": session, "name": term_name, "start": start, "end": end, "next": next_begins}

    if domain == "historical_enrollments":
        student = _student_for(school, row["student_ref"])
        session = _session_for(school, row["session"])
        arm = _arm_for(school, row["class_level"], row["class_arm"])
        enrolled = _date(row["enrolled_on"], "enrolled_on")
        exited = _date(row.get("exited_on", ""), "exited_on")
        status = row["status"].strip().casefold()
        reason = row.get("entry_reason", "migration").strip().casefold() or "migration"
        if status not in dict(SessionEnrollment.STATUS_CHOICES):
            raise ValueError("status", "Use active, completed, withdrawn, transferred or graduated.")
        if reason not in dict(SessionEnrollment.ENTRY_REASON_CHOICES):
            raise ValueError("entry_reason", "Use admission, promotion, repeat, migration, manual or transfer.")
        if status == "active":
            if not session.is_current:
                raise ValueError("status", "Only the current session may receive an active historical placement.")
            if exited:
                raise ValueError("exited_on", "Active placement cannot have an exit date.")
        elif not exited:
            raise ValueError("exited_on", "Closed historical placement requires an exit date.")
        exact = SessionEnrollment.objects.filter(
            school=school, student=student, session=session, class_arm=arm,
            enrolled_on=enrolled, exited_on=exited, status=status
        ).first()
        if exact:
            return "REUSE", {}
        proposed_end = exited or session.end_date
        conflicts = SessionEnrollment.objects.filter(
            school=school, student=student, session=session,
            enrolled_on__lte=proposed_end,
        ).filter(models.Q(exited_on__isnull=True) | models.Q(exited_on__gte=enrolled))
        if conflicts.exists():
            raise MigrationReview(
                "enrolled_on",
                "This placement overlaps existing enrollment history.",
                conflict_type="placement_overlap",
                candidates=[{"id": p.pk, "class": p.class_arm.full_name,
                             "enrolled_on": str(p.enrolled_on), "exited_on": str(p.exited_on or "")}
                            for p in conflicts.select_related("class_arm__class_level")[:5]],
            )
        return "CREATE", {"student": student, "session": session, "arm": arm,
                          "enrolled": enrolled, "exited": exited, "status": status, "reason": reason}

    if domain == "historical_results":
        student = _student_for(school, row["student_ref"])
        session = _session_for(school, row["session"])
        term = _term_for(session, row["term"])
        arm = _arm_for(school, row["class_level"], row["class_arm"])
        placement = SessionEnrollment.objects.filter(
            school=school, student=student, session=session, class_arm=arm,
            enrolled_on__lte=term.end_date,
        ).filter(models.Q(exited_on__isnull=True) | models.Q(exited_on__gte=term.start_date)).first()
        if not placement:
            raise ValueError("class_arm", "Student placement history does not support this result.")
        subject = Subject.objects.filter(school=school, code__iexact=row["subject_code"]).first()
        if not subject:
            raise ValueError("subject_code", "Import this subject first.")
        values = {field: _decimal_score(row, field) for field in
                  ("first_test", "second_test", "assignment", "project", "practical", "exam_score")}
        ca_total = sum((values[field] for field in
                        ("first_test", "second_test", "assignment", "project", "practical")), Decimal("0"))
        if ca_total > Decimal(str(subject.max_ca_score)):
            raise ValueError("first_test", f"Continuous assessment total exceeds this subject's {subject.max_ca_score}-mark CA limit.")
        if values["exam_score"] > Decimal(str(subject.max_exam_score)):
            raise ValueError("exam_score", f"Exam score exceeds this subject's {subject.max_exam_score}-mark exam limit.")
        if ca_total + values["exam_score"] > Decimal("100.00"):
            raise ValueError("exam_score", "Assessment components total more than 100.")
        published_text = row.get("is_published", "").strip().casefold()
        published = published_text in ("1", "true", "yes", "published")
        existing = ScoreEntry.objects.filter(
            school=school, student=student.user, subject=subject, term=term, session=session
        ).first()
        if existing:
            same = all(getattr(existing, field) == value for field, value in values.items())
            if same and existing.class_arm_id == arm.pk and existing.is_published == published:
                return "REUSE", {}
            raise MigrationReview("student_ref", "A result already exists with different values.",
                                  conflict_type="result_conflict",
                                  candidates=[{"id": existing.pk, "total_score": str(existing.total_score)}])
        return "CREATE", {"student": student, "session": session, "term": term, "arm": arm,
                          "subject": subject, "values": values, "published": published}

    if domain == "historical_finance":
        student = _student_for(school, row["student_ref"])
        effective = _date(row["effective_date"], "effective_date")
        description = row["description"].strip()
        reference = row["reference"].strip()
        if not description or len(description) > 500:
            raise ValueError("description", "Provide a description of up to 500 characters.")
        if not reference or len(reference) > 100:
            raise ValueError("reference", "Provide a source reference of up to 100 characters.")
        try:
            debit = Decimal(str(row.get("debit") or "0"))
            credit = Decimal(str(row.get("credit") or "0"))
        except Exception:
            raise ValueError("debit", "Debit and credit must be valid amounts.")
        for field, amount in (("debit", debit), ("credit", credit)):
            if not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
                raise ValueError(field, "Use a nonnegative amount with at most two decimal places.")
        if (debit > 0) == (credit > 0):
            raise ValueError("debit", "Enter exactly one positive debit or credit amount.")
        account = StudentFinanceAccount.objects.filter(school=school, student=student).first()
        if not account or account.state != "active":
            raise MigrationReview(
                "student_ref",
                "Verify this student's opening balance before importing historical finance adjustments.",
                conflict_type="finance_account_not_ready",
            )
        term = None
        if row.get("session") or row.get("term"):
            if not row.get("session") or not row.get("term"):
                raise ValueError("term", "Provide both session and term, or leave both blank.")
            session = _session_for(school, row["session"])
            term = _term_for(session, row["term"])
        signed = debit if debit > 0 else -credit
        ref_digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()[:48]
        key = f"migration-finance:{school.pk}:{student.pk}:{ref_digest}"
        existing = StudentLedgerEntry.objects.filter(school=school, idempotency_key=key).first()
        if existing:
            if (
                existing.student_id == student.pk
                and existing.kind == "adjustment"
                and existing.signed_amount == signed
                and existing.reason == description
                and existing.reference == reference
                and existing.effective_date == effective
                and existing.term_id == (term.pk if term else None)
            ):
                return "REUSE", {}
            raise MigrationReview(
                "reference",
                "This source reference already exists with different financial details.",
                conflict_type="finance_reference_conflict",
                candidates=[{"id": existing.pk, "signed_amount": str(existing.signed_amount)}],
            )
        return "CREATE", {
            "student": student, "effective": effective, "description": description,
            "reference": reference, "signed": signed, "term": term, "key": key,
        }

    if domain == "historical_attendance":
        student = _student_for(school, row["student_ref"])
        session = _session_for(school, row["session"])
        term = _term_for(session, row["term"])
        day = _date(row["date"], "date")
        if not day or day < term.start_date or day > term.end_date:
            raise ValueError("date", "Attendance date must fall within the selected term.")
        arm = _arm_for(school, row["class_level"], row["class_arm"])
        placement = SessionEnrollment.objects.filter(
            school=school, student=student, session=session, class_arm=arm, enrolled_on__lte=day
        ).filter(models.Q(exited_on__isnull=True) | models.Q(exited_on__gte=day)).first()
        if not placement:
            raise ValueError("class_arm", "Student placement history does not support attendance on this date.")
        status = row["status"].strip().casefold()
        aliases = {"p": "present", "a": "absent", "l": "late", "e": "excused"}
        status = aliases.get(status, status)
        if status not in dict(AttendanceRecord.Status.choices):
            raise ValueError("status", "Use present, absent, late or excused.")
        attendance_session = AttendanceSession.objects.filter(
            school=school, class_arm=arm, term=term, date=day,
            mode=AttendanceSession.Mode.DAILY, period__isnull=True
        ).first()
        if attendance_session:
            existing = AttendanceRecord.objects.filter(
                attendance_session=attendance_session, student=student.user
            ).first()
            if existing:
                if existing.status == status and existing.remark == row.get("remark", "")[:255]:
                    return "REUSE", {}
                raise MigrationReview("status", "Attendance already exists with a different value.",
                                      conflict_type="attendance_conflict",
                                      candidates=[{"id": existing.pk, "status": existing.status}])
        return "CREATE", {"student": student, "term": term, "arm": arm, "day": day,
                          "status": status, "remark": row.get("remark", "")[:255]}

    raise ValueError("file", "Unsupported historical migration type.")


def create_batch20(domain, row, school, data, *, actor=None):
    if domain == "historical_sessions":
        return AcademicSession.objects.create(
            school=school, name=data["name"], start_date=data["start"], end_date=data["end"], is_current=False
        )
    elif domain == "historical_terms":
        return Term.objects.create(
            session=data["session"], name=data["name"], start_date=data["start"],
            end_date=data["end"], next_term_begins=data["next"], is_current=False
        )
    elif domain == "historical_enrollments":
        enrollment = SessionEnrollment.objects.create(
            school=school, student=data["student"], session=data["session"], class_arm=data["arm"],
            status=data["status"], entry_reason=data["reason"], enrolled_on=data["enrolled"],
            exited_on=data["exited"], notes="Imported historical placement.", created_by=actor
        )
        # Only an active placement in the current session may become the convenience pointer.
        if data["status"] == "active" and data["session"].is_current:
            student = data["student"]
            if student.current_class_id not in (None, data["arm"].pk):
                raise MigrationReview("class_arm", "Current class conflicts with imported active placement.",
                                      conflict_type="current_class_conflict")
            student.current_class = data["arm"]
            student.save(update_fields=["current_class"])
        return enrollment
    elif domain == "historical_results":
        return ScoreEntry.objects.create(
            school=school, student=data["student"].user, subject=data["subject"],
            class_arm=data["arm"], session=data["session"], term=data["term"],
            is_published=data["published"], **data["values"]
        )
    elif domain == "historical_finance":
        entry, _ = post_adjustment(
            school, data["student"], actor, kind="adjustment",
            amount=data["signed"], reason=data["description"], key=data["key"],
            term=data["term"], reference=data["reference"], effective_date=data["effective"],
        )
        return entry
    elif domain == "historical_attendance":
        attendance_session, _ = AttendanceSession.objects.get_or_create(
            school=school, class_arm=data["arm"], term=data["term"], date=data["day"],
            mode=AttendanceSession.Mode.DAILY, period=None,
            defaults={"teacher": None, "is_finalized": True},
        )
        return AttendanceRecord.objects.create(
            attendance_session=attendance_session, student=data["student"].user,
            status=data["status"], remark=data["remark"]
        )
    else:
        raise ValueError("file", "Unsupported historical migration type.")

