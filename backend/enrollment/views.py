"""
enrollment/views.py

StudentViewSet with:
  - Standard CRUD (list, create, retrieve, partial_update)
  - POST bulk-import/  — CSV upload with per-row error reporting
  - POST {id}/assign-class/
  - GET  by-class/{class_arm_id}/

Also: ClassLevelViewSet, ClassArmViewSet, SubjectViewSet
"""

import csv
import io
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts.permissions import IsSchoolAdmin, IsSchoolAdminOrTeacher, IsAuthenticatedTenantUser
from tenants.mixins import TenantMixin
from .safety import RetainAcademicHistoryMixin

from .models import ClassArm, ClassLevel, StudentProfile, Subject
from .session_enrollment import EnrollmentPlacementError, ensure_current_enrollment
from .lifecycle import StudentLifecycleError, transition_student
from .transfers import StudentTransferError, transfer_student
from .serializers import (
    ClassArmSerializer,
    ClassLevelSerializer,
    StudentListSerializer,
    StudentProfileSerializer,
    SubjectSerializer,
)

User = get_user_model()

# ── CSV column config ──────────────────────────────────────────────────────

REQUIRED_CSV_COLS = {
    "first_name", "last_name",
    "gender", "dob", "class_level",
    "guardian_name", "guardian_phone",
}


def _parse_date(val: str):
    """Try YYYY-MM-DD and DD/MM/YYYY formats."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            from datetime import datetime
            return datetime.strptime(val, fmt).date()
        except ValueError:
            continue
    return None


# ── ClassLevel ViewSet ─────────────────────────────────────────────────────

class ClassLevelViewSet(RetainAcademicHistoryMixin, TenantMixin, viewsets.ModelViewSet):
    serializer_class = ClassLevelSerializer
    queryset         = ClassLevel.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]


# ── ClassArm ViewSet ───────────────────────────────────────────────────────

class ClassArmViewSet(RetainAcademicHistoryMixin, TenantMixin, viewsets.ModelViewSet):
    serializer_class = ClassArmSerializer
    queryset         = ClassArm.objects.select_related(
        "class_level", "class_teacher"
    ).prefetch_related("students")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()
        level = self.request.query_params.get("class_level")
        if level:
            qs = qs.filter(class_level_id=level)
        return qs


# ── Subject ViewSet ────────────────────────────────────────────────────────

class SubjectViewSet(RetainAcademicHistoryMixin, TenantMixin, viewsets.ModelViewSet):
    serializer_class = SubjectSerializer
    queryset         = Subject.objects.prefetch_related("class_levels")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]


# ── Student ViewSet ────────────────────────────────────────────────────────

class StudentViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    GET    /api/students/              list (with search + status filter)
    POST   /api/students/              create single student
    GET    /api/students/{id}/         retrieve
    PATCH  /api/students/{id}/         partial update
    POST   /api/students/bulk-import/  CSV bulk create
    POST   /api/students/{id}/assign-class/
    GET    /api/students/by-class/{class_arm_id}/
    """

    filter_backends  = [filters.SearchFilter, filters.OrderingFilter]
    search_fields    = [
        "user__first_name", "user__last_name",
        "user__email", "admission_number",
    ]
    ordering_fields  = ["admission_number", "user__last_name", "admission_date"]
    ordering         = ["user__last_name"]

    queryset = StudentProfile.objects.select_related(
        "user", "school", "current_class", "current_class__class_level"
    )

    def perform_destroy(self, instance):
        from rest_framework.exceptions import ValidationError
        raise ValidationError('Student history must be retained. Change the enrollment status instead of deleting the student.')

    @action(detail=True, methods=['post'], parser_classes=[MultiPartParser], url_path='photo')
    def photo(self, request, pk=None):
        from tenants.image_uploads import store_uploaded_image
        student = self.get_object()
        url = store_uploaded_image(request.FILES.get('photo'), f'student-photos/{request.tenant.pk}/{student.pk}')
        student.user.profile_photo = url
        student.user.save(update_fields=['profile_photo'])
        return Response({'profile_photo': url})

    def get_serializer_class(self):
        if self.action == "list":
            return StudentListSerializer
        return StudentProfileSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve", "by_class"):
            return [IsSchoolAdminOrTeacher()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()

        # Status filter: ?status=active
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Class filter: ?class_arm=5
        class_arm = self.request.query_params.get("class_arm")
        if class_arm:
            qs = qs.filter(current_class_id=class_arm)

        # Class level filter: ?class_level=JSS1
        class_level = self.request.query_params.get("class_level")
        if class_level:
            qs = qs.filter(current_class__class_level__name=class_level)

        return qs

    # ── List by class arm ────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path=r"by-class/(?P<class_arm_id>\d+)")
    def by_class(self, request, class_arm_id=None):
        """GET /api/students/by-class/{class_arm_id}/"""
        tenant = self._get_tenant()

        try:
            arm = ClassArm.objects.get(pk=class_arm_id, school=tenant)
        except ClassArm.DoesNotExist:
            return Response(
                {"error": "Class arm not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        students = StudentProfile.objects.filter(
            school=tenant,
            current_class=arm,
            status="active",
        ).select_related("user", "current_class__class_level")

        serializer = StudentListSerializer(students, many=True)
        return Response({
            "class":   ClassArmSerializer(arm).data,
            "count":   students.count(),
            "results": serializer.data,
        })

    # ── Controlled lifecycle ──────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="lifecycle")
    def lifecycle(self, request, pk=None):
        student = self.get_object()
        action_name = request.data.get("action")
        reason = request.data.get("reason", "")
        effective_date = request.data.get("effective_date")

        if effective_date not in (None, ""):
            effective_date = _parse_date(str(effective_date))
            if not effective_date:
                return Response(
                    {"error": "Enter a valid effective_date in YYYY-MM-DD format."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            effective_date = None

        try:
            updated = transition_student(
                school=self._get_tenant(),
                student=student,
                action=action_name,
                actor=request.user,
                effective_date=effective_date,
                reason=reason,
            )
        except StudentLifecycleError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated.refresh_from_db()
        return Response(
            StudentProfileSerializer(
                updated,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )

    # ── Mid-session class transfer ───────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="transfer-class")
    def transfer_class(self, request, pk=None):
        student = self.get_object()
        tenant = self._get_tenant()
        class_arm_id = request.data.get("class_arm")
        effective_raw = request.data.get("effective_date")
        reason = request.data.get("reason", "")

        if not class_arm_id:
            return Response(
                {"error": "class_arm is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not effective_raw:
            return Response(
                {"error": "effective_date is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        effective_date = _parse_date(str(effective_raw))
        if not effective_date:
            return Response(
                {"error": "Enter a valid effective_date in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            destination = ClassArm.objects.get(
                pk=class_arm_id,
                school=tenant,
            )
        except ClassArm.DoesNotExist:
            return Response(
                {"error": "Destination class not found for this school."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            updated, source, destination_enrollment = transfer_student(
                school=tenant,
                student=student,
                destination_class=destination,
                effective_date=effective_date,
                actor=request.user,
                reason=reason,
            )
        except StudentTransferError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated.refresh_from_db()
        return Response(
            {
                "student": StudentProfileSerializer(
                    updated,
                    context={"request": request},
                ).data,
                "source_enrollment": {
                    "id": source.pk,
                    "class_arm": source.class_arm_id,
                    "status": source.status,
                    "enrolled_on": source.enrolled_on,
                    "exited_on": source.exited_on,
                },
                "destination_enrollment": {
                    "id": destination_enrollment.pk,
                    "class_arm": destination_enrollment.class_arm_id,
                    "status": destination_enrollment.status,
                    "enrolled_on": destination_enrollment.enrolled_on,
                    "exited_on": destination_enrollment.exited_on,
                },
            },
            status=status.HTTP_200_OK,
        )

    # ── Assign class ─────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="assign-class")
    def assign_class(self, request, pk=None):
        """
        POST /api/students/{id}/assign-class/
        Body: { "class_arm": <id> }
        """
        student = self.get_object()
        tenant  = self._get_tenant()

        class_arm_id = request.data.get("class_arm")
        if not class_arm_id:
            return Response(
                {"error": "class_arm is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            arm = ClassArm.objects.get(pk=class_arm_id, school=tenant)
        except ClassArm.DoesNotExist:
            return Response(
                {"error": "Class arm not found for this school."},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            ensure_current_enrollment(
                school=tenant,
                student=student,
                class_arm=arm,
                actor=request.user,
                entry_reason="manual",
            )
        except EnrollmentPlacementError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student.refresh_from_db()
        return Response(
            StudentProfileSerializer(student, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    # ── Bulk CSV import ───────────────────────────────────────────────────

    @action(
        detail=False,
        methods=["post"],
        url_path="bulk-import",
        parser_classes=[MultiPartParser],
    )
    def bulk_import(self, request):
        """
        POST /api/students/bulk-import/
        Form field: file (CSV)

        CSV columns (header row required):
          first_name, last_name, gender, dob,
          class_level, guardian_name, guardian_phone
          Optional: email, state_of_origin, religion, guardian_email,
                    guardian_relationship

        Returns:
          {
            "success_count": 12,
            "error_count": 2,
            "errors": [
              { "row": 5, "reason": "Email already exists." },
              { "row": 9, "reason": "Invalid date format for dob." }
            ]
          }
        """
        tenant    = self._get_tenant()
        csv_file  = request.FILES.get("file")

        if not csv_file:
            return Response(
                {"error": "No file uploaded. Send a CSV as field 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not csv_file.name.lower().endswith(".csv"):
            return Response(
                {"error": "Only .csv files are accepted."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Decode bytes → text
        try:
            content = csv_file.read().decode("utf-8-sig")  # handle BOM from Excel
        except UnicodeDecodeError:
            return Response(
                {"error": "File encoding not supported. Save as UTF-8 CSV."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reader      = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            return Response({'error':'CSV headers must be present and unique.'}, status=400)
        if any(key in reader.fieldnames for key in ('admission_number','student_id','staff_id','school','school_id','user','user_id')):
            return Response({'error':'Identifiers are generated by Paideia. Remove identifier/school columns; imports create new records only.'}, status=400)
        headers     = set(reader.fieldnames or [])
        missing     = REQUIRED_CSV_COLS - headers

        if missing:
            return Response(
                {
                    "error": f"Missing required columns: {', '.join(sorted(missing))}",
                    "required": sorted(REQUIRED_CSV_COLS),
                    "found":    sorted(headers),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Cache class levels for fast lookup ────────────────────────────
        level_map = {
            cl.name.lower(): cl
            for cl in ClassLevel.objects.filter(school=tenant)
        }
        # Cache all arms per level
        arm_map = {}
        for arm in ClassArm.objects.filter(school=tenant).select_related("class_level"):
            arm_map.setdefault(arm.class_level.name.lower(), []).append(arm)

        from academics.models import AcademicSession
        current_session = AcademicSession.objects.filter(
            school=tenant, is_current=True
        ).first()

        success_count = 0
        errors        = []

        for row_num, row in enumerate(reader, start=2):  # row 1 = header

            def add_error(reason):
                errors.append({"row": row_num, "reason": reason})

            # ── Required field presence ───────────────────────────────────
            if None in row or any(value is None for value in row.values()):
                add_error('Column count does not match the header.'); continue
            email      = (row.get("email")      or "").strip().lower()
            first_name = (row.get("first_name") or "").strip()
            last_name  = (row.get("last_name")  or "").strip()
            gender     = (row.get("gender")     or "").strip().lower()
            dob_raw    = (row.get("dob")        or "").strip()
            level_name = (row.get("class_level")or "").strip().lower()

            # Email is optional for student accounts.
            if not first_name: add_error("first_name is empty.");  continue
            if not last_name:  add_error("last_name is empty.");   continue

            if email:
                from django.core.validators import validate_email
                from django.core.exceptions import ValidationError
                try:
                    validate_email(email)
                except ValidationError:
                    add_error('Enter a valid email address.'); continue

            # ── Validate email uniqueness ─────────────────────────────────
            if email and User.objects.filter(email__iexact=email).exists():
                add_error("This email cannot be used. Check the account details."); continue

            # ── Validate gender ───────────────────────────────────────────
            if gender not in ("male", "female", "m", "f", ""):
                add_error(f"Invalid gender '{gender}'. Use male/female."); continue
            gender = "male" if gender in ("m", "male") else "female" if gender in ("f", "female") else ""

            # ── Parse DOB ─────────────────────────────────────────────────
            dob = None
            if dob_raw:
                dob = _parse_date(dob_raw)
                if not dob:
                    add_error(f"Invalid date format '{dob_raw}'. Use YYYY-MM-DD or DD/MM/YYYY.")
                    continue

            # ── Resolve class level → first available arm ─────────────────
            if level_name not in level_map:
                add_error(f"Class level '{row.get('class_level')}' not found for this school.")
                continue

            level      = level_map[level_name]
            level_arms = arm_map.get(level_name, [])
            arm_name = (row.get('class_arm') or '').strip().casefold()
            matches = [arm for arm in level_arms if not arm_name or arm.name.casefold() == arm_name or arm.full_name.casefold() == arm_name]
            if len(matches) > 1 or (arm_name and len(matches) != 1):
                add_error('Select one existing class arm using the class_arm column; no student was created.')
                continue
            class_arm = matches[0] if matches else None
            if StudentProfile.objects.filter(school=tenant, user__first_name__iexact=first_name,
                    user__last_name__iexact=last_name, dob=dob, current_class=class_arm).exists():
                add_error('A student with this name, date of birth and class already exists. Review the record before adding individually.')
                continue

            # ── Create user + profile in a savepoint ──────────────────────
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email,
                        password="changeme",
                        first_name=first_name,
                        last_name=last_name,
                        role="student",
                        school=tenant,
                        must_change_password=True,
                    )
                    profile = StudentProfile.objects.create(
                        user=user,
                        school=tenant,
                        dob=dob,
                        gender=gender,
                        current_class=None,
                        state_of_origin=(row.get("state_of_origin") or "").strip(),
                        religion=(row.get("religion") or "").strip(),
                        guardian_name=(row.get("guardian_name") or "").strip(),
                        guardian_phone=(row.get("guardian_phone") or "").strip(),
                        guardian_email=(row.get("guardian_email") or "").strip().lower(),
                        guardian_relationship=(row.get("guardian_relationship") or "").strip().lower(),
                    )
                    if class_arm:
                        ensure_current_enrollment(
                            school=tenant,
                            student=profile,
                            class_arm=class_arm,
                            actor=request.user,
                            entry_reason="admission",
                            current_session=current_session,
                        )
                    # Set password to admission number
                    user.set_password(profile.admission_number)
                    user.save(update_fields=["password"])

                success_count += 1

            except EnrollmentPlacementError as exc:
                add_error(str(exc))
            except Exception:
                add_error('This row could not be imported. Check its values and retry.')

        return Response(
            {
                "success_count": success_count,
                "error_count":   len(errors),
                "errors":        errors,
            },
            status=status.HTTP_200_OK,
        )
