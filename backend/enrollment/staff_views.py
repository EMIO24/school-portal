"""
enrollment/staff_views.py

StaffViewSet — CRUD + bulk CSV import + assignment actions.

Endpoints:
  GET/POST   /api/staff/
  GET/PATCH  /api/staff/{id}/
  POST       /api/staff/bulk-import/
  POST       /api/staff/{id}/assign-subjects/
  POST       /api/staff/{id}/assign-classes/
  GET        /api/staff/by-role/?role=teacher
"""

import csv
import io

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts.permissions import IsSchoolAdmin, IsAuthenticatedTenantUser
from tenants.mixins import TenantMixin

from .models import ClassArm, StaffProfile, Subject
from .staff_serializers import StaffListSerializer, StaffProfileSerializer

User = get_user_model()

REQUIRED_STAFF_CSV_COLS = {
    "first_name", "last_name", "email", "role",
}


class StaffViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Full CRUD for StaffProfile (teachers + school admins).
    """

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields   = [
        "user__first_name", "user__last_name",
        "user__email", "staff_id", "specialization",
    ]
    ordering_fields  = ["staff_id", "user__last_name", "date_employed"]
    ordering         = ["user__last_name"]

    queryset = StaffProfile.objects.select_related(
        "user", "school"
    ).prefetch_related("subjects_taught", "assigned_classes")

    def get_serializer_class(self):
        return StaffListSerializer if self.action == "list" else StaffProfileSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve", "by_role"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        qs = super().get_queryset()

        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(user__role=role)

        status_f = self.request.query_params.get("status")
        if status_f:
            qs = qs.filter(employment_status=status_f)

        return qs

    # ── Filter by role ────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="by-role")
    def by_role(self, request):
        """GET /api/staff/by-role/?role=teacher"""
        role = request.query_params.get("role", "teacher")
        qs   = self.get_queryset().filter(user__role=role)
        ser  = StaffListSerializer(qs, many=True)
        return Response({"count": qs.count(), "results": ser.data})

    # ── Assign subjects ───────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="assign-subjects")
    def assign_subjects(self, request, pk=None):
        """
        POST /api/staff/{id}/assign-subjects/
        Body: { "subjects": [1, 2, 3] }
        """
        staff   = self.get_object()
        tenant  = self._get_tenant()
        ids     = request.data.get("subjects", [])

        subjects = Subject.objects.filter(pk__in=ids, school=tenant)
        if len(subjects) != len(ids):
            return Response(
                {"error": "One or more subject IDs are invalid for this school."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        staff.subjects_taught.set(subjects)
        return Response(StaffProfileSerializer(staff).data)

    # ── Assign classes ────────────────────────────────────────────────────

    @action(detail=True, methods=["post"], url_path="assign-classes")
    def assign_classes(self, request, pk=None):
        """
        POST /api/staff/{id}/assign-classes/
        Body: { "classes": [1, 2] }
        """
        staff  = self.get_object()
        tenant = self._get_tenant()
        ids    = request.data.get("classes", [])

        arms = ClassArm.objects.filter(pk__in=ids, school=tenant)
        if len(arms) != len(ids):
            return Response(
                {"error": "One or more class arm IDs are invalid for this school."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        staff.assigned_classes.set(arms)
        return Response(StaffProfileSerializer(staff).data)

    # ── Bulk CSV import ───────────────────────────────────────────────────

    @action(
        detail=False, methods=["post"],
        url_path="bulk-import",
        parser_classes=[MultiPartParser],
    )
    def bulk_import(self, request):
        """
        POST /api/staff/bulk-import/
        Form field: file (CSV)

        Required columns: first_name, last_name, email, role
        Optional:  gender, dob, phone, qualification, specialization,
                   date_employed, state_of_origin

        Returns: { success_count, error_count, errors:[{row, reason}] }
        """
        tenant   = self._get_tenant()
        csv_file = request.FILES.get("file")

        if not csv_file:
            return Response({"error": "No file uploaded."}, status=400)
        if not csv_file.name.endswith(".csv"):
            return Response({"error": "Only .csv files accepted."}, status=400)

        try:
            content = csv_file.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response({"error": "Unsupported encoding. Save as UTF-8 CSV."}, status=400)

        reader  = csv.DictReader(io.StringIO(content))
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_STAFF_CSV_COLS - headers

        if missing:
            return Response({
                "error": f"Missing required columns: {', '.join(sorted(missing))}",
                "required": sorted(REQUIRED_STAFF_CSV_COLS),
            }, status=400)

        success_count = 0
        errors        = []

        VALID_ROLES = {"school_admin", "teacher"}

        for row_num, row in enumerate(reader, start=2):
            def add_error(reason):
                errors.append({"row": row_num, "reason": reason})

            email      = (row.get("email")      or "").strip().lower()
            first_name = (row.get("first_name") or "").strip()
            last_name  = (row.get("last_name")  or "").strip()
            role       = (row.get("role")       or "").strip().lower()

            if not email:      add_error("email is empty.");      continue
            if not first_name: add_error("first_name is empty."); continue
            if not last_name:  add_error("last_name is empty.");  continue
            if role not in VALID_ROLES:
                add_error(f"role '{role}' invalid. Use: school_admin or teacher."); continue
            if User.objects.filter(email=email).exists():
                add_error(f"Email '{email}' already exists."); continue

            # Parse optional date fields
            from datetime import date as _date
            def _parse_date(val):
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
                    try:
                        from datetime import datetime
                        return datetime.strptime(val, fmt).date()
                    except (ValueError, TypeError):
                        continue
                return None

            dob_raw       = (row.get("dob")           or "").strip()
            employed_raw  = (row.get("date_employed")  or "").strip()
            dob           = _parse_date(dob_raw)       if dob_raw      else None
            date_employed = _parse_date(employed_raw)  if employed_raw else None

            if dob_raw and not dob:
                add_error(f"Invalid dob format '{dob_raw}'. Use YYYY-MM-DD."); continue
            if employed_raw and not date_employed:
                add_error(f"Invalid date_employed format '{employed_raw}'."); continue

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        email=email,
                        password="changeme",
                        first_name=first_name,
                        last_name=last_name,
                        role=role,
                        school=tenant,
                        must_change_password=True,
                    )
                    profile = StaffProfile.objects.create(
                        user=user, school=tenant,
                        dob=dob,
                        date_employed=date_employed,
                        gender=(row.get("gender") or "").strip().lower() or "",
                        phone=(row.get("phone") or "").strip(),
                        qualification=(row.get("qualification") or "").strip().lower(),
                        specialization=(row.get("specialization") or "").strip(),
                        state_of_origin=(row.get("state_of_origin") or "").strip(),
                    )
                    user.set_password(profile.staff_id)
                    user.save(update_fields=["password"])

                success_count += 1
            except Exception as exc:
                add_error(str(exc))

        return Response({
            "success_count": success_count,
            "error_count":   len(errors),
            "errors":        errors,
        })