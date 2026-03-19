"""
academics/views.py

ViewSets for the academic calendar.

All standard ViewSets use TenantMixin — querysets are automatically
scoped to request.tenant and school is injected on create.

Custom actions:
  POST /api/sessions/{id}/set-current/  → marks a session as current
  POST /api/terms/{id}/set-current/     → marks a term as current
  GET  /api/calendar/current/           → returns active session + term
"""

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsSchoolAdmin, IsAuthenticatedTenantUser
from tenants.mixins import TenantMixin

from .models import AcademicSession, Holiday, Term
from .serializers import (
    AcademicSessionSerializer,
    CurrentCalendarSerializer,
    HolidaySerializer,
    TermSerializer,
)


class SessionViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    CRUD for AcademicSession + set-current action.

    list/retrieve — any authenticated school user
    create/update/delete/set-current — school_admin only
    """

    serializer_class = AcademicSessionSerializer
    queryset         = AcademicSession.objects.prefetch_related(
        "terms", "terms__holidays"
    )

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]

    # TenantMixin.get_queryset() filters by school automatically.
    # We add ordering here for clarity.
    def get_queryset(self):
        return super().get_queryset().order_by("-start_date")

    @action(detail=True, methods=["post"], url_path="set-current")
    def set_current(self, request, pk=None):
        """
        POST /api/sessions/{id}/set-current/

        Marks this session as the current one.
        The model's save() atomically clears the flag on all others.
        """
        session = self.get_object()
        session.is_current = True
        session.save()
        return Response(
            AcademicSessionSerializer(session).data,
            status=status.HTTP_200_OK,
        )


class TermViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    CRUD for Term + set-current action.

    Terms must belong to a session in the current tenant.
    TenantMixin filters via Term.session__school.
    """

    serializer_class = TermSerializer
    queryset         = Term.objects.select_related("session").prefetch_related("holidays")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        """
        Override TenantMixin to filter through session FK instead of a
        direct school FK (Term has no direct school FK).
        """
        tenant = self._get_tenant()
        qs = Term.objects.select_related("session").prefetch_related("holidays")
        qs = qs.filter(session__school=tenant)

        # Optional: filter by session via ?session=<id>
        session_id = self.request.query_params.get("session")
        if session_id:
            qs = qs.filter(session_id=session_id)

        return qs.order_by("session__start_date", "name")

    def perform_create(self, serializer):
        """
        Validate that the session belongs to the current tenant before saving.
        """
        session = serializer.validated_data.get("session")
        tenant  = self._get_tenant()
        if session and session.school != tenant:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Session does not belong to this school.")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="set-current")
    def set_current(self, request, pk=None):
        """
        POST /api/terms/{id}/set-current/

        Marks this term as current. Model.save() enforces school-scope.
        Also marks the parent session as current for consistency.
        """
        term = self.get_object()
        term.is_current = True
        term.save()

        # Ensure parent session is also current
        session = term.session
        if not session.is_current:
            session.is_current = True
            session.save()

        return Response(
            TermSerializer(term).data,
            status=status.HTTP_200_OK,
        )


class HolidayViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    CRUD for Holiday.
    Scoped via term__session__school.
    """

    serializer_class = HolidaySerializer
    queryset         = Holiday.objects.select_related("term__session")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        tenant = self._get_tenant()
        qs     = Holiday.objects.select_related("term__session").filter(
            term__session__school=tenant
        )
        term_id = self.request.query_params.get("term")
        if term_id:
            qs = qs.filter(term_id=term_id)
        return qs.order_by("start_date")

    def perform_create(self, serializer):
        """Validate that the term belongs to this tenant."""
        term   = serializer.validated_data.get("term")
        tenant = self._get_tenant()
        if term and term.session.school != tenant:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Term does not belong to this school.")
        serializer.save()


class CurrentCalendarView(TenantMixin, viewsets.ViewSet):
    """
    GET /api/calendar/current/

    Returns the active session and active term for the current tenant.
    No model manipulation — read-only snapshot.
    Used by the frontend on app load to set context.
    """

    permission_classes = [IsAuthenticatedTenantUser]

    def list(self, request):
        tenant = self._get_tenant()

        session = AcademicSession.objects.filter(
            school=tenant, is_current=True
        ).prefetch_related("terms", "terms__holidays").first()

        term = Term.objects.filter(
            session__school=tenant, is_current=True
        ).select_related("session").prefetch_related("holidays").first()

        if not session and not term:
            return Response(
                {
                    "detail": "No current session or term configured.",
                    "session": None,
                    "term": None,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "session": AcademicSessionSerializer(session).data if session else None,
                "term":    TermSerializer(term).data if term else None,
            }
        )