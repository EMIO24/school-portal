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
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction

from accounts.permissions import IsSchoolAdmin, IsAuthenticatedTenantUser
from tenants.mixins import TenantMixin
from tenants.security import audit

from .models import AcademicRollover, AcademicSession, Holiday, Term
from .serializers import (
    AcademicSessionSerializer,
    CurrentCalendarSerializer,
    HolidaySerializer,
    TermSerializer,
)


from enrollment.safety import RetainAcademicHistoryMixin
from .history import session_has_execution_history, term_has_execution_history
from .rollover import RolloverSafetyError, activate_session, activate_term, execute_rollover, prepare_rollover_preview


class SessionViewSet(RetainAcademicHistoryMixin, TenantMixin, viewsets.ModelViewSet):
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

    def perform_update(self, serializer):
        instance = serializer.instance
        protected = ("name", "start_date", "end_date")
        changed = any(
            field in serializer.validated_data and serializer.validated_data[field] != getattr(instance, field)
            for field in protected
        )
        if changed and session_has_execution_history(instance):
            raise ValidationError("This academic session has historical records and its identity or dates cannot be changed.")
        serializer.save()

    @action(detail=False, methods=["get"], url_path="rollover-history")
    def rollover_history(self, request):
        """Return the school's auditable rollover history, newest first."""
        rows = AcademicRollover.objects.filter(
            school=self._get_tenant()
        ).select_related(
            "source_session",
            "destination_session",
            "created_by",
            "completed_by",
        ).order_by("-created_at", "-id")[:50]

        return Response([
            {
                "id": row.pk,
                "status": row.status,
                "source_session": {
                    "id": row.source_session_id,
                    "name": row.source_session.name,
                },
                "destination_session": {
                    "id": row.destination_session_id,
                    "name": row.destination_session.name,
                },
                "student_count": row.student_count,
                "promoted_count": row.promoted_count,
                "repeated_count": row.repeated_count,
                "graduated_count": row.graduated_count,
                "withdrawn_count": row.withdrawn_count,
                "snapshot_fingerprint": (
                    row.configuration_options.get("snapshot_fingerprint")
                    if isinstance(row.configuration_options, dict) else None
                ),
                "created_at": row.created_at.isoformat(),
                "created_by": row.created_by.email if row.created_by else None,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "completed_by": row.completed_by.email if row.completed_by else None,
            }
            for row in rows
        ])

    @action(detail=True, methods=["post"], url_path="rollover-preview")
    def rollover_preview(self, request, pk=None):
        """Build a non-destructive readiness preview for this source session."""
        source = self.get_object()
        destination_id = request.data.get("destination_session_id")
        destination = AcademicSession.objects.filter(
            pk=destination_id,
            school=self._get_tenant(),
        ).first()
        if not destination:
            raise ValidationError({
                "destination_session_id": "Select a destination session belonging to this school."
            })
        try:
            preview = prepare_rollover_preview(
                school=self._get_tenant(),
                source_session=source,
                destination_session=destination,
                actor=request.user,
            )
        except RolloverSafetyError as exc:
            raise ValidationError(str(exc))
        return Response(preview, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="rollover-execute")
    def rollover_execute(self, request, pk=None):
        """Atomically execute a ready rollover from this source session."""
        source = self.get_object()
        destination_id = request.data.get("destination_session_id")
        destination = AcademicSession.objects.filter(
            pk=destination_id,
            school=self._get_tenant(),
        ).first()
        if not destination:
            raise ValidationError({
                "destination_session_id": "Select a destination session belonging to this school."
            })

        idempotency_key = str(request.data.get("idempotency_key") or "").strip()
        if len(idempotency_key) > 100:
            raise ValidationError({
                "idempotency_key": "Idempotency key must be 100 characters or fewer."
            })

        try:
            result = execute_rollover(
                school=self._get_tenant(),
                source_session=source,
                destination_session=destination,
                actor=request.user,
                idempotency_key=idempotency_key,
            )
        except RolloverSafetyError as exc:
            raise ValidationError(str(exc))
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="set-current")
    @transaction.atomic
    def set_current(self, request, pk=None):
        """
        POST /api/sessions/{id}/set-current/

        Marks this session as the current one.
        The model's save() atomically clears the flag on all others.
        """
        session = self.get_object()
        try:
            session = activate_session(school=self._get_tenant(), target_session=session)
        except RolloverSafetyError as exc:
            raise ValidationError(str(exc))
        return Response(AcademicSessionSerializer(session).data, status=status.HTTP_200_OK)


class TermViewSet(RetainAcademicHistoryMixin, TenantMixin, viewsets.ModelViewSet):
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

    def perform_update(self, serializer):
        instance = serializer.instance
        session = serializer.validated_data.get("session", instance.session)
        if session.school_id != self._get_tenant().pk:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Session does not belong to this school.")
        protected = ("session", "name", "start_date", "end_date", "next_term_begins")
        changed = any(
            field in serializer.validated_data and serializer.validated_data[field] != getattr(instance, field)
            for field in protected
        )
        if changed and term_has_execution_history(instance):
            raise ValidationError("This term has historical execution records and its calendar meaning cannot be changed.")
        serializer.save()

    @action(detail=True, methods=["post"], url_path="set-current")
    @transaction.atomic
    def set_current(self, request, pk=None):
        """
        POST /api/terms/{id}/set-current/

        Marks this term as current. Model.save() enforces school-scope.
        Also marks the parent session as current for consistency.
        """
        term = self.get_object()
        try:
            term = activate_term(school=self._get_tenant(), target_term=term)
        except RolloverSafetyError as exc:
            raise ValidationError(str(exc))
        return Response(TermSerializer(term).data, status=status.HTTP_200_OK)


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
        holiday = serializer.save()
        audit(self.request, 'calendar.holiday_created', target=f'holiday:{holiday.pk}', details={
            'school_id': tenant.pk, 'term_id': holiday.term_id})

    def perform_update(self, serializer):
        holiday = serializer.instance
        before = {name: getattr(holiday, name) for name in ('term_id', 'name', 'start_date', 'end_date', 'holiday_type')}
        after = {name: serializer.validated_data.get('term').pk if name == 'term_id' and 'term' in serializer.validated_data else
                 serializer.validated_data.get(name, value) for name, value in before.items()}
        changed = [name for name in before if before[name] != after[name]]
        if not changed:
            return
        if holiday.start_date <= timezone.localdate():
            raise ValidationError('A started holiday is historical and cannot be changed.')
        serializer.save()
        audit(self.request, 'calendar.holiday_changed', target=f'holiday:{holiday.pk}', details={
            'school_id': self._get_tenant().pk, 'term_id': holiday.term_id, 'changed_fields': changed})

    def perform_destroy(self, instance):
        if instance.start_date <= timezone.localdate():
            raise ValidationError('A started holiday is historical and cannot be deleted.')
        audit(self.request, 'calendar.holiday_deleted', target=f'holiday:{instance.pk}', details={
            'school_id': self._get_tenant().pk, 'term_id': instance.term_id})
        instance.delete()


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
