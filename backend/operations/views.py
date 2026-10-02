import secrets
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from enrollment.class_structure import ClassStructureError, resolve_class_for_admission
from enrollment.models import ClassArm, ClassLevel, StudentProfile
from enrollment.serializers import StudentProfileSerializer
from tenants.models import Campus
from tenants.security import audit

from .models import AdmissionApplication, AdmissionDocument, StudentRecordEntry, WelfareCase, WelfareCaseUpdate
from .serializers import AdmissionApplicationSerializer, AdmissionDocumentSerializer, StudentRecordEntrySerializer, WelfareCaseSerializer


def _school_staff(request):
    school = getattr(request, "tenant", None)
    return bool(
        school and request.user.is_authenticated and request.user.is_active
        and request.user.school_id == school.pk and not request.user.must_change_password
    )


def _management(request):
    return _school_staff(request) and request.user.role in ("school_admin", "principal")


def _application_number(school):
    year = timezone.localdate().year
    for _ in range(8):
        value = f"ADM-{year}-{secrets.token_hex(3).upper()}"
        if not AdmissionApplication.objects.filter(school=school, application_number=value).exists():
            return value
    raise RuntimeError("Could not allocate application number.")


class AdmissionApplicationListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _management(request):
            return Response({"detail": "School management access required."}, status=403)
        qs = AdmissionApplication.objects.filter(school=request.tenant).select_related(
            "applying_class_level", "preferred_campus", "admitted_student__user"
        ).prefetch_related("documents")
        state = request.query_params.get("status")
        if state:
            qs = qs.filter(status=state)
        return Response(AdmissionApplicationSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        if not _management(request):
            return Response({"detail": "School management access required."}, status=403)
        form = AdmissionApplicationSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        level = form.validated_data["applying_class_level"]
        campus = form.validated_data.get("preferred_campus")
        if level.school_id != request.tenant.pk:
            return Response({"applying_class_level": "Choose a class level in this school."}, status=400)
        if campus and campus.school_id != request.tenant.pk:
            return Response({"preferred_campus": "Choose a campus in this school."}, status=400)
        if campus and request.tenant.subscription_plan != "enterprise":
            return Response({"preferred_campus": "Campus selection requires Enterprise."}, status=403)
        row = form.save(
            school=request.tenant,
            application_number=_application_number(request.tenant),
            created_by=request.user,
        )
        audit(request, "admission.application_created", target=f"admission:{row.pk}",
              details={"school_id": request.tenant.pk, "application_number": row.application_number})
        return Response(AdmissionApplicationSerializer(row).data, status=201)


class AdmissionApplicationDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _management(request):
            return Response({"detail": "School management access required."}, status=403)
        row = AdmissionApplication.objects.filter(pk=pk, school=request.tenant).prefetch_related("documents").first()
        return Response(AdmissionApplicationSerializer(row).data) if row else Response(status=404)

    @transaction.atomic
    def patch(self, request, pk):
        if not _management(request):
            return Response({"detail": "School management access required."}, status=403)
        row = AdmissionApplication.objects.select_for_update().filter(pk=pk, school=request.tenant).first()
        if not row:
            return Response(status=404)
        if row.status in (AdmissionApplication.Status.ADMITTED, AdmissionApplication.Status.REJECTED, AdmissionApplication.Status.WITHDRAWN):
            return Response({"detail": "Closed applications cannot be edited."}, status=409)
        form = AdmissionApplicationSerializer(row, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        level = form.validated_data.get("applying_class_level", row.applying_class_level)
        campus = form.validated_data.get("preferred_campus", row.preferred_campus)
        if level.school_id != request.tenant.pk or (campus and campus.school_id != request.tenant.pk):
            return Response({"detail": "Admission references must belong to this school."}, status=400)
        row = form.save()
        audit(request, "admission.application_updated", target=f"admission:{row.pk}",
              details={"school_id": request.tenant.pk})
        return Response(AdmissionApplicationSerializer(row).data)


class AdmissionDocumentCreate(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _management(request):
            return Response({"detail": "School management access required."}, status=403)
        app = AdmissionApplication.objects.filter(pk=pk, school=request.tenant).first()
        if not app:
            return Response(status=404)
        form = AdmissionDocumentSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        row = form.save(application=app, uploaded_by=request.user)
        audit(request, "admission.document_added", target=f"admission-document:{row.pk}",
              details={"school_id": request.tenant.pk, "application_id": app.pk, "kind": row.kind})
        return Response(AdmissionDocumentSerializer(row).data, status=201)


class AdmissionDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _management(request):
            return Response({"detail": "School management access required."}, status=403)
        app = AdmissionApplication.objects.select_for_update().select_related(
            "applying_class_level", "preferred_campus", "admitted_student"
        ).filter(pk=pk, school=request.tenant).first()
        if not app:
            return Response(status=404)

        decision = request.data.get("decision")
        if decision not in ("under_review", "offered", "admit", "reject", "withdraw"):
            return Response({"decision": "Choose under_review, offered, admit, reject or withdraw."}, status=400)

        if app.status == AdmissionApplication.Status.ADMITTED:
            if decision == "admit":
                return Response(AdmissionApplicationSerializer(app).data)
            return Response({"detail": "An admitted application cannot be reopened."}, status=409)
        if app.status in (AdmissionApplication.Status.REJECTED, AdmissionApplication.Status.WITHDRAWN):
            return Response({"detail": "This application is already closed."}, status=409)

        if decision != "admit":
            mapping = {
                "under_review": AdmissionApplication.Status.UNDER_REVIEW,
                "offered": AdmissionApplication.Status.OFFERED,
                "reject": AdmissionApplication.Status.REJECTED,
                "withdraw": AdmissionApplication.Status.WITHDRAWN,
            }
            app.status = mapping[decision]
            app.reviewed_by = request.user
            app.reviewed_at = timezone.now()
            app.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
            audit(request, "admission.decision_recorded", target=f"admission:{app.pk}",
                  details={"school_id": request.tenant.pk, "decision": decision})
            return Response(AdmissionApplicationSerializer(app).data)

        class_arm = None
        raw_arm = request.data.get("class_arm")
        if raw_arm not in (None, ""):
            class_arm = ClassArm.objects.filter(pk=raw_arm, school=request.tenant).first()
            if not class_arm:
                return Response({"class_arm": "Choose a class in this school."}, status=400)

        campus = app.preferred_campus
        raw_campus = request.data.get("campus")
        if raw_campus not in (None, ""):
            campus = Campus.objects.filter(pk=raw_campus, school=request.tenant).first()
            if not campus:
                return Response({"campus": "Choose a campus in this school."}, status=400)

        try:
            placement = resolve_class_for_admission(
                school=request.tenant,
                class_level=app.applying_class_level,
                class_arm=class_arm,
                campus=campus,
            )
        except ClassStructureError as exc:
            return Response({"class_arm": str(exc)}, status=400)

        payload = {
            "new_first_name": app.first_name,
            "new_last_name": app.last_name,
            "dob": app.dob,
            "gender": app.gender,
            "current_class": placement.pk,
            "guardian_name": app.guardian_name,
            "guardian_phone": app.guardian_phone,
            "guardian_email": app.guardian_email,
            "guardian_relationship": "guardian",
        }
        form = StudentProfileSerializer(data=payload, context={"request": request})
        form.is_valid(raise_exception=True)
        student = form.save(school=request.tenant)

        StudentRecordEntry.objects.create(
            school=request.tenant,
            student=student,
            kind=StudentRecordEntry.Kind.ENROLLMENT,
            title=f"Admitted through {app.application_number}",
            details=f"Admission application converted to student record. Initial class: {placement.full_name}.",
            effective_date=timezone.localdate(),
            recorded_by=request.user,
        )
        app.status = AdmissionApplication.Status.ADMITTED
        app.admitted_student = student
        app.reviewed_by = request.user
        app.reviewed_at = timezone.now()
        app.save(update_fields=["status", "admitted_student", "reviewed_by", "reviewed_at", "updated_at"])
        audit(request, "admission.student_admitted", target=f"student:{student.pk}",
              details={"school_id": request.tenant.pk, "application_id": app.pk, "class_arm_id": placement.pk})
        return Response(AdmissionApplicationSerializer(app).data, status=201)


class StudentRecordListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        if not _management(request):
            return Response({"detail": "School management access required."}, status=403)
        student = StudentProfile.objects.filter(pk=student_id, school=request.tenant).first()
        if not student:
            return Response(status=404)
        rows = StudentRecordEntry.objects.filter(school=request.tenant, student=student).select_related("recorded_by")
        return Response(StudentRecordEntrySerializer(rows, many=True).data)

    @transaction.atomic
    def post(self, request, student_id):
        if not _management(request):
            return Response({"detail": "School management access required."}, status=403)
        student = StudentProfile.objects.filter(pk=student_id, school=request.tenant).first()
        if not student:
            return Response(status=404)
        form = StudentRecordEntrySerializer(data=request.data)
        form.is_valid(raise_exception=True)
        prior = form.validated_data.get("supersedes")
        if prior and (prior.school_id != request.tenant.pk or prior.student_id != student.pk):
            return Response({"supersedes": "Correction target must belong to this student record."}, status=400)
        row = form.save(school=request.tenant, student=student, recorded_by=request.user)
        audit(request, "student_record.entry_added", target=f"student-record:{row.pk}",
              details={"school_id": request.tenant.pk, "student_id": student.pk, "kind": row.kind})
        return Response(StudentRecordEntrySerializer(row).data, status=201)


def _welfare_queryset(request):
    qs = WelfareCase.objects.filter(school=request.tenant).select_related(
        "student__user", "class_arm_snapshot__class_level", "assigned_to"
    ).prefetch_related("updates__created_by")
    if request.user.role == "class_teacher":
        qs = qs.filter(class_arm_snapshot__class_teacher=request.user).exclude(
            category__in=[WelfareCase.Category.HEALTH, WelfareCase.Category.SAFEGUARDING]
        )
    return qs


def _welfare_allowed(request):
    return _school_staff(request) and request.user.role in ("school_admin", "principal", "class_teacher")


class WelfareCaseListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _welfare_allowed(request):
            return Response({"detail": "Student welfare access required."}, status=403)
        qs = _welfare_queryset(request)
        state = request.query_params.get("status")
        if state:
            qs = qs.filter(status=state)
        return Response(WelfareCaseSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request):
        if not _welfare_allowed(request):
            return Response({"detail": "Student welfare access required."}, status=403)
        student = StudentProfile.objects.select_related("current_class__class_level").filter(
            pk=request.data.get("student"), school=request.tenant
        ).first()
        if not student:
            return Response({"student": "Choose a student in this school."}, status=400)
        if request.user.role == "class_teacher":
            if not student.current_class_id or student.current_class.class_teacher_id != request.user.pk:
                return Response({"detail": "Class Teachers can open cases only for their own class."}, status=403)
            if request.data.get("category") in (WelfareCase.Category.HEALTH, WelfareCase.Category.SAFEGUARDING):
                return Response({"category": "Sensitive welfare cases require Principal or School Admin."}, status=403)
        form = WelfareCaseSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        row = form.save(
            school=request.tenant,
            class_arm_snapshot=student.current_class,
            opened_by=request.user,
        )
        audit(request, "welfare.case_opened", target=f"welfare:{row.pk}",
              details={"school_id": request.tenant.pk, "student_id": student.pk, "severity": row.severity})
        return Response(WelfareCaseSerializer(row).data, status=201)


class WelfareCaseDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _welfare_allowed(request):
            return Response({"detail": "Student welfare access required."}, status=403)
        row = _welfare_queryset(request).filter(pk=pk).first()
        return Response(WelfareCaseSerializer(row).data) if row else Response(status=404)


class WelfareCaseUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        if not _welfare_allowed(request):
            return Response({"detail": "Student welfare access required."}, status=403)
        row = _welfare_queryset(request).select_for_update().filter(pk=pk).first()
        if not row:
            return Response(status=404)
        note = str(request.data.get("note") or "").strip()
        state = request.data.get("status", row.status)
        if not note:
            return Response({"note": "Enter an update note."}, status=400)
        if state not in WelfareCase.Status.values:
            return Response({"status": "Choose open, monitoring or resolved."}, status=400)
        WelfareCaseUpdate.objects.create(case=row, note=note, status_after=state, created_by=request.user)
        row.status = state
        row.resolved_at = timezone.now() if state == WelfareCase.Status.RESOLVED else None
        row.save(update_fields=["status", "resolved_at", "updated_at"])
        audit(request, "welfare.case_updated", target=f"welfare:{row.pk}",
              details={"school_id": request.tenant.pk, "status": state})
        return Response(WelfareCaseSerializer(row).data)
