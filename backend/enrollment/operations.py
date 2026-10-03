"""Batches 22–23 operational APIs: admissions, official records and welfare."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tenants.security import audit
from .class_structure import ClassStructureError, resolve_class_for_admission
from .models import (
    AdmissionApplication, AdmissionDocument, ClassArm, ClassLevel, StudentProfile,
    StudentRecordEntry, WelfareCase, WelfareUpdate,
)
from .serializers import StudentProfileSerializer
from .placement_lock import lock_school


def _school_user(request, roles):
    school = getattr(request, "tenant", None)
    user = request.user
    return bool(
        school and user.is_authenticated and user.is_active and not user.must_change_password
        and user.school_id == school.pk and user.role in roles
    )


def _error_dict(exc):
    if hasattr(exc, "message_dict"):
        return exc.message_dict
    return {"detail": getattr(exc, "messages", [str(exc)])}


def _admission_data(row):
    return {
        "id": row.pk,
        "application_number": row.application_number,
        "first_name": row.first_name,
        "last_name": row.last_name,
        "email": row.email,
        "dob": row.dob,
        "gender": row.gender,
        "guardian_name": row.guardian_name,
        "guardian_phone": row.guardian_phone,
        "guardian_email": row.guardian_email,
        "previous_school": row.previous_school,
        "applying_class_level": row.applying_class_level_id,
        "applying_class_level_name": row.applying_class_level.name,
        "preferred_campus": row.preferred_campus_id,
        "preferred_campus_name": row.preferred_campus.name if row.preferred_campus else "",
        "notes": row.notes,
        "status": row.status,
        "admitted_student": row.admitted_student_id,
        "decided_at": row.decided_at,
        "created_at": row.created_at,
        "documents": [
            {
                "id": doc.pk, "kind": doc.kind, "title": doc.title,
                "document_url": doc.document_url, "created_at": doc.created_at,
            }
            for doc in row.documents.all()
        ],
    }


class AdmissionListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _school_user(request, ("school_admin", "principal")):
            return Response({"detail": "Admissions access required."}, status=403)
        qs = AdmissionApplication.objects.filter(school=request.tenant).select_related(
            "applying_class_level", "preferred_campus", "admitted_student__user"
        ).prefetch_related("documents")
        status_value = request.query_params.get("status")
        if status_value:
            if status_value not in dict(AdmissionApplication.STATUS_CHOICES):
                return Response({"status": "Choose a valid admission status."}, status=400)
            qs = qs.filter(status=status_value)
        return Response([_admission_data(row) for row in qs[:2000]])

    @transaction.atomic
    def post(self, request):
        if not _school_user(request, ("school_admin", "principal")):
            return Response({"detail": "Admissions access required."}, status=403)
        school = request.tenant
        first = str(request.data.get("first_name") or "").strip()
        last = str(request.data.get("last_name") or "").strip()
        guardian = str(request.data.get("guardian_name") or "").strip()
        phone = str(request.data.get("guardian_phone") or "").strip()
        if not first or not last or not guardian or not phone:
            return Response({"detail": "First name, last name, guardian name and guardian phone are required."}, status=400)
        level_id = request.data.get("applying_class_level")
        if not str(level_id or "").isdigit():
            return Response({"applying_class_level": "Choose a valid class level."}, status=400)
        level = ClassLevel.objects.filter(pk=level_id, school=school).first()
        if not level:
            return Response({"applying_class_level": "Choose a class level in this school."}, status=400)
        campus = None
        campus_id = request.data.get("preferred_campus")
        if campus_id not in (None, ""):
            if not str(campus_id).isdigit():
                return Response({"preferred_campus": "Choose a valid campus."}, status=400)
            campus = school.campuses.filter(pk=campus_id, is_active=True).first()
            if not campus:
                return Response({"preferred_campus": "Choose an active campus in this school."}, status=400)
        dob = request.data.get("dob")
        parsed_dob = parse_date(str(dob)) if dob else None
        if dob and not parsed_dob:
            return Response({"dob": "Use YYYY-MM-DD."}, status=400)
        gender = str(request.data.get("gender") or "")
        if gender not in ("", "male", "female"):
            return Response({"gender": "Choose male or female."}, status=400)
        row = AdmissionApplication(
            school=school,
            first_name=first[:150],
            last_name=last[:150],
            email=str(request.data.get("email") or "").strip().lower(),
            dob=parsed_dob,
            gender=gender,
            guardian_name=guardian[:150],
            guardian_phone=phone[:20],
            guardian_email=str(request.data.get("guardian_email") or "").strip().lower(),
            previous_school=str(request.data.get("previous_school") or "").strip()[:180],
            applying_class_level=level,
            preferred_campus=campus,
            notes=str(request.data.get("notes") or "").strip(),
            created_by=request.user,
        )
        try:
            row.full_clean()
            row.save()
        except DjangoValidationError as exc:
            return Response(_error_dict(exc), status=400)
        audit(request, "admissions.application_created", target=f"admission:{row.pk}",
              details={"school_id": school.pk, "class_level_id": level.pk, "campus_id": campus.pk if campus else None})
        return Response(_admission_data(row), status=201)


class AdmissionDocumentCreate(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _school_user(request, ("school_admin", "principal")):
            return Response({"detail": "Admissions document access required."}, status=403)
        application = AdmissionApplication.objects.filter(pk=pk, school=request.tenant).first()
        if not application:
            return Response(status=404)
        kind = str(request.data.get("kind") or "")
        title = str(request.data.get("title") or "").strip()
        document_url = str(request.data.get("document_url") or "").strip()
        if kind not in dict(AdmissionDocument.KIND_CHOICES):
            return Response({"kind": "Choose a valid document type."}, status=400)
        if not title or not document_url:
            return Response({"detail": "Document title and URL are required."}, status=400)
        row = AdmissionDocument(
            application=application, kind=kind, title=title[:180],
            document_url=document_url, uploaded_by=request.user,
        )
        try:
            row.full_clean()
            row.save()
        except DjangoValidationError as exc:
            return Response(_error_dict(exc), status=400)
        audit(request, "admissions.document_added", target=f"admission-document:{row.pk}",
              details={"school_id": request.tenant.pk, "application_id": application.pk, "kind": kind})
        application = AdmissionApplication.objects.prefetch_related("documents").get(pk=application.pk)
        return Response(_admission_data(application), status=201)


class AdmissionDecision(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _school_user(request, ("school_admin", "principal")):
            return Response({"detail": "Admissions decision access required."}, status=403)
        school = lock_school(request.tenant)
        row = AdmissionApplication.objects.select_for_update(of=("self",)).select_related(
            "applying_class_level", "preferred_campus", "admitted_student__user"
        ).filter(pk=pk, school=school).first()
        if not row:
            return Response(status=404)
        decision = request.data.get("decision")
        if decision not in ("under_review", "offered", "admit", "reject", "withdraw"):
            return Response({"decision": "Choose under_review, offered, admit, reject or withdraw."}, status=400)
        if row.status in ("admitted", "rejected", "withdrawn"):
            if row.status == "admitted" and decision == "admit":
                student = row.admitted_student
                if (not student or student.school_id != school.pk
                        or student.user.school_id != school.pk
                        or not student.session_enrollments.filter(school=school, entry_reason="admission").exists()
                        or not StudentRecordEntry.objects.filter(school=school, student=student, kind="enrollment",
                            details=f"Created from admission application {row.application_number}.").exists()):
                    return Response({"detail": "Admission history is incomplete; review explicitly before retrying."}, status=409)
                return Response(_admission_data(row))
            return Response({"detail": "This application already has a terminal decision."}, status=409)

        if decision != "admit":
            target = {
                "under_review": "under_review",
                "offered": "offered",
                "reject": "rejected",
                "withdraw": "withdrawn",
            }[decision]
            row.status = target
            if target in ("rejected", "withdrawn"):
                row.decided_by = request.user
                row.decided_at = timezone.now()
            row.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
            audit(request, "admissions.application_" + target, target=f"admission:{row.pk}",
                  details={"school_id": school.pk})
            return Response(_admission_data(row))

        class_arm = None
        raw_arm = request.data.get("class_arm")
        if raw_arm not in (None, ""):
            if not str(raw_arm).isdigit():
                return Response({"class_arm": "Choose a valid class."}, status=400)
            class_arm = ClassArm.objects.filter(pk=raw_arm, school=school).select_related("class_level", "campus").first()
            if not class_arm:
                return Response({"class_arm": "Choose a class in this school."}, status=400)
        campus = row.preferred_campus
        raw_campus = request.data.get("campus")
        if raw_campus not in (None, ""):
            if not str(raw_campus).isdigit():
                return Response({"campus": "Choose a valid campus."}, status=400)
            campus = school.campuses.filter(pk=raw_campus, is_active=True).first()
            if not campus:
                return Response({"campus": "Choose an active campus in this school."}, status=400)
        try:
            destination = resolve_class_for_admission(
                school=school,
                class_level=row.applying_class_level,
                class_arm=class_arm,
                campus=campus,
            )
        except ClassStructureError as exc:
            return Response({"class_arm": str(exc)}, status=400)

        student_payload = {
            "new_first_name": row.first_name,
            "new_last_name": row.last_name,
            "new_email": row.email,
            "dob": row.dob.isoformat() if row.dob else None,
            "gender": row.gender,
            "current_class": destination.pk,
            "guardian_name": row.guardian_name,
            "guardian_phone": row.guardian_phone,
            "guardian_email": row.guardian_email,
            "guardian_relationship": "guardian",
        }
        serializer = StudentProfileSerializer(data=student_payload, context={"request": request})
        serializer.is_valid(raise_exception=True)
        student = serializer.save(school=school)
        row.status = "admitted"
        row.admitted_student = student
        row.decided_by = request.user
        row.decided_at = timezone.now()
        row.save(update_fields=["status", "admitted_student", "decided_by", "decided_at", "updated_at"])
        StudentRecordEntry.objects.create(
            school=school, student=student, kind="enrollment",
            title="Admission to " + destination.full_name,
            details=f"Created from admission application {row.application_number}.",
            effective_date=timezone.localdate(), created_by=request.user,
        )
        audit(request, "admissions.student_admitted", target=f"student:{student.pk}",
              details={"school_id": school.pk, "application_id": row.pk, "class_arm_id": destination.pk})
        return Response(_admission_data(row), status=201)


def _record_data(row):
    return {
        "id": row.pk, "student": row.student_id, "kind": row.kind, "title": row.title,
        "details": row.details, "document_url": row.document_url,
        "effective_date": row.effective_date, "supersedes": row.supersedes_id,
        "created_by": row.created_by_id, "created_at": row.created_at,
    }


class StudentRecordHistory(APIView):
    permission_classes = [IsAuthenticated]

    def _student(self, request, student_id):
        return StudentProfile.objects.filter(pk=student_id, school=request.tenant).first()

    def get(self, request, student_id):
        if not _school_user(request, ("school_admin", "principal")):
            return Response({"detail": "Official student-record access required."}, status=403)
        student = self._student(request, student_id)
        if not student:
            return Response(status=404)
        qs = StudentRecordEntry.objects.filter(school=request.tenant, student=student).select_related("created_by", "supersedes")
        return Response([_record_data(row) for row in qs])

    @transaction.atomic
    def post(self, request, student_id):
        if not _school_user(request, ("school_admin", "principal")):
            return Response({"detail": "Official student-record access required."}, status=403)
        student = self._student(request, student_id)
        if not student:
            return Response(status=404)
        kind = request.data.get("kind")
        if kind not in dict(StudentRecordEntry.KIND_CHOICES):
            return Response({"kind": "Choose a valid record type."}, status=400)
        title = str(request.data.get("title") or "").strip()
        if not title or len(title) > 180:
            return Response({"title": "Provide a title up to 180 characters."}, status=400)
        effective_date = parse_date(str(request.data.get("effective_date") or ""))
        if not effective_date:
            return Response({"effective_date": "Use YYYY-MM-DD."}, status=400)
        supersedes = None
        raw_supersedes = request.data.get("supersedes")
        if raw_supersedes not in (None, ""):
            if not str(raw_supersedes).isdigit():
                return Response({"supersedes": "Choose a valid earlier record."}, status=400)
            supersedes = StudentRecordEntry.objects.filter(
                pk=raw_supersedes, school=request.tenant, student=student
            ).first()
            if not supersedes:
                return Response({"supersedes": "Choose an earlier record for this student."}, status=400)
        row = StudentRecordEntry(
            school=request.tenant, student=student, kind=kind, title=title,
            details=str(request.data.get("details") or "").strip(),
            document_url=str(request.data.get("document_url") or "").strip(),
            effective_date=effective_date, supersedes=supersedes, created_by=request.user,
        )
        try:
            row.full_clean()
            row.save()
        except DjangoValidationError as exc:
            return Response(_error_dict(exc), status=400)
        audit(request, "records.student_entry_added", target=f"student-record:{row.pk}",
              details={"school_id": request.tenant.pk, "student_id": student.pk, "kind": kind,
                       "supersedes": supersedes.pk if supersedes else None})
        return Response(_record_data(row), status=201)


def _welfare_data(row):
    return {
        "id": row.pk, "student": row.student_id, "student_name": row.student.full_name,
        "class_arm": row.class_arm_snapshot_id,
        "class_name": row.class_arm_snapshot.full_name if row.class_arm_snapshot else "",
        "category": row.category, "severity": row.severity, "title": row.title,
        "details": row.details, "status": row.status, "is_sensitive": row.is_sensitive,
        "reported_by": row.reported_by_id, "resolved_by": row.resolved_by_id,
        "resolved_at": row.resolved_at, "created_at": row.created_at,
        "updates": [
            {"id": update.pk, "note": update.note, "status_after": update.status_after,
             "created_by": update.created_by_id, "created_at": update.created_at}
            for update in row.updates.all()
        ],
    }


def _class_teacher_student(request, student):
    return bool(
        request.user.role == "class_teacher"
        and student.current_class_id
        and student.current_class.school_id == request.tenant.pk
        and student.current_class.class_teacher_id == request.user.pk
    )


def _welfare_queryset(request):
    """Scope cases before loading private history, including historical class."""
    qs = WelfareCase.objects.filter(
        school=request.tenant, student__school=request.tenant,
        student__user__school=request.tenant,
    ).filter(
        Q(class_arm_snapshot__isnull=True) | Q(class_arm_snapshot__school=request.tenant)
    )
    if request.user.role == "class_teacher":
        qs = qs.filter(
            class_arm_snapshot__school=request.tenant,
            class_arm_snapshot_id=F("student__current_class_id"),
            class_arm_snapshot__class_teacher=request.user,
        ).exclude(category__in=("health", "safeguarding"))
    return qs


class WelfareListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _school_user(request, ("school_admin", "principal", "class_teacher")):
            return Response({"detail": "Student welfare access required."}, status=403)
        qs = _welfare_queryset(request).select_related(
            "student__user", "student__current_class__class_level",
            "class_arm_snapshot__class_level", "reported_by", "resolved_by",
        ).prefetch_related("updates__created_by")
        raw_status = request.query_params.get("status")
        if raw_status:
            if raw_status not in dict(WelfareCase.STATUS_CHOICES):
                return Response({"status": "Choose a valid welfare status."}, status=400)
            qs = qs.filter(status=raw_status)
        return Response([_welfare_data(row) for row in qs[:2000]])

    @transaction.atomic
    def post(self, request):
        if not _school_user(request, ("school_admin", "principal", "class_teacher")):
            return Response({"detail": "Student welfare access required."}, status=403)
        student_id = request.data.get("student")
        if not str(student_id or "").isdigit():
            return Response({"student": "Choose a valid student."}, status=400)
        student = StudentProfile.objects.select_related("current_class__class_level", "user").filter(
            pk=student_id, school=request.tenant, user__school=request.tenant, status="active"
        ).filter(Q(current_class__isnull=True) | Q(current_class__school=request.tenant)).first()
        if not student:
            return Response({"student": "Choose an active student in this school."}, status=400)
        category = request.data.get("category")
        severity = request.data.get("severity")
        if category not in dict(WelfareCase.CATEGORY_CHOICES):
            return Response({"category": "Choose a valid welfare category."}, status=400)
        if severity not in dict(WelfareCase.SEVERITY_CHOICES):
            return Response({"severity": "Choose a valid severity."}, status=400)
        if request.user.role == "class_teacher":
            if not _class_teacher_student(request, student):
                return Response({"detail": "This student is not in your class."}, status=403)
            if category in ("health", "safeguarding"):
                return Response({"detail": "Health and safeguarding cases are restricted to school management."}, status=403)
        title = str(request.data.get("title") or "").strip()
        details = str(request.data.get("details") or "").strip()
        if not title or len(title) > 180 or not details:
            return Response({"detail": "Provide a case title and details."}, status=400)
        row = WelfareCase(
            school=request.tenant, student=student, class_arm_snapshot=student.current_class,
            category=category, severity=severity, title=title, details=details,
            reported_by=request.user,
        )
        try:
            row.full_clean()
            row.save()
        except DjangoValidationError as exc:
            return Response(_error_dict(exc), status=400)
        audit(request, "welfare.case_opened", target=f"welfare:{row.pk}",
              details={"school_id": request.tenant.pk, "student_id": student.pk,
                       "category": category, "severity": severity})
        return Response(_welfare_data(row), status=201)


class WelfareUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _school_user(request, ("school_admin", "principal", "class_teacher")):
            return Response({"detail": "Student welfare access required."}, status=403)
        # Lock only the case; nullable class joins cannot be locked on PostgreSQL.
        row = _welfare_queryset(request).select_for_update(of=("self",)).select_related(
            "student__user", "student__current_class__class_level", "class_arm_snapshot__class_level"
        ).prefetch_related("updates__created_by").filter(pk=pk).first()
        if not row:
            return Response(status=404)
        note = str(request.data.get("note") or "").strip()
        status_after = request.data.get("status", row.status)
        if not note:
            return Response({"note": "Provide an update note."}, status=400)
        if status_after not in dict(WelfareCase.STATUS_CHOICES):
            return Response({"status": "Choose open, monitoring or resolved."}, status=400)
        status_before = row.status
        update = WelfareUpdate.objects.create(
            welfare_case=row, note=note, status_after=status_after, created_by=request.user
        )
        if row.status != status_after:
            row.status = status_after
            if status_after == "resolved":
                row.resolved_by = request.user
                row.resolved_at = timezone.now()
            else:
                row.resolved_by = None
                row.resolved_at = None
            row.save(update_fields=["status", "resolved_by", "resolved_at", "updated_at"])
        audit(request, "welfare.case_updated", target=f"welfare:{row.pk}",
              details={"school_id": request.tenant.pk, "student_id": row.student_id,
                       "status": status_after, "status_before": status_before,
                       "update_id": update.pk})
        row.refresh_from_db()
        return Response(_welfare_data(row))
