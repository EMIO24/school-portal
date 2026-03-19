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

from .models import ClassArm, ClassLevel, StudentProfile, Subject
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
    "first_name", "last_name", "email",
    "gender", "dob", "class_level",
    "guardian_name", "guardian_phone",
}


def _parse_date(val: str):
    """Try YYYY-MM-DD and DD/MM/YYYY formats."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return date.fromisoformat(val) if fmt == "%Y-%m-%d" else date.strptime(val, fmt)
        except ValueError:
            continue
    return None


# ── ClassLevel ViewSet ─────────────────────────────────────────────────────

class ClassLevelViewSet(TenantMixin, viewsets.ModelViewSet):
    serializer_class = ClassLevelSerializer
    queryset         = ClassLevel.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]


# ── ClassArm ViewSet ───────────────────────────────────────────────────────

class ClassArmViewSet(TenantMixin, viewsets.ModelViewSet):
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

class SubjectViewSet(TenantMixin, viewsets.ModelViewSet):
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

        student.current_class = arm
        student.save(update_fields=["current_class"])

        return Response(
            StudentProfileSerializer(student).data,
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
          first_name, last_name, email, gender, dob,
          class_level, guardian_name, guardian_phone
          Optional: state_of_origin, religion, guardian_email,
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

        if not csv_file.name.endswith(".csv"):
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

        success_count = 0
        errors        = []

        for row_num, row in enumerate(reader, start=2):  # row 1 = header

            def add_error(reason):
                errors.append({"row": row_num, "reason": reason})

            # ── Required field presence ───────────────────────────────────
            email      = (row.get("email")      or "").strip().lower()
            first_name = (row.get("first_name") or "").strip()
            last_name  = (row.get("last_name")  or "").strip()
            gender     = (row.get("gender")     or "").strip().lower()
            dob_raw    = (row.get("dob")        or "").strip()
            level_name = (row.get("class_level")or "").strip().lower()

            if not email:      add_error("email is empty.");       continue
            if not first_name: add_error("first_name is empty.");  continue
            if not last_name:  add_error("last_name is empty.");   continue

            # ── Validate email uniqueness ─────────────────────────────────
            if User.objects.filter(email=email).exists():
                add_error(f"Email '{email}' already exists."); continue

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
            class_arm  = level_arms[0] if level_arms else None

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
                        current_class=class_arm,
                        state_of_origin=(row.get("state_of_origin") or "").strip(),
                        religion=(row.get("religion") or "").strip(),
                        guardian_name=(row.get("guardian_name") or "").strip(),
                        guardian_phone=(row.get("guardian_phone") or "").strip(),
                        guardian_email=(row.get("guardian_email") or "").strip().lower(),
                        guardian_relationship=(row.get("guardian_relationship") or "").strip().lower(),
                    )
                    # Set password to admission number
                    user.set_password(profile.admission_number)
                    user.save(update_fields=["password"])

                success_count += 1

            except Exception as exc:
                add_error(str(exc))

        return Response(
            {
                "success_count": success_count,
                "error_count":   len(errors),
                "errors":        errors,
            },
            status=status.HTTP_200_OK,
        )