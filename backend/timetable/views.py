"""
backend/timetable/views.py

ViewSets for Period and TimetableEntry.

All ViewSets inherit TenantMixin which:
  • sets  self.school = request.tenant
  • injects school into serializer context
  • never allows cross-tenant data leakage

Endpoint summary (registered in urls.py):
  /timetable/periods/                              PeriodViewSet  (CRUD)
  /timetable/entries/                              TimetableEntryViewSet
  /timetable/entries/grid/?class_arm=&term=        one-shot grid payload
  /timetable/entries/by-class/<id>/?term=          class grid
  /timetable/entries/by-teacher/<id>/?term=        teacher grid
  /timetable/entries/my-timetable/?term=           logged-in teacher
  /timetable/entries/teacher-load/?teacher=&term=  daily load counts
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from tenants.mixins import TenantMixin
from .models import Period, TimetableEntry
from .serializers import (
    PeriodSerializer,
    TimetableEntryReadSerializer,
    TimetableEntryWriteSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _base_entry_qs(school):
    """Pre-fetch every relation the read serializer needs."""
    return (
        TimetableEntry.objects
        .filter(school=school)
        .select_related(
            'period',
            'class_arm',
            'subject',
            'subject__category',
            'teacher',
            'term',
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# PeriodViewSet
# ─────────────────────────────────────────────────────────────────────────────

class PeriodViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    CRUD for time-slot configuration.
    school_admin: full CRUD.  All other roles: read-only.
    """
    serializer_class   = PeriodSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Period.objects.filter(school=self.school).order_by('order_index')

    def perform_create(self, serializer):
        serializer.save(school=self.school)


# ─────────────────────────────────────────────────────────────────────────────
# TimetableEntryViewSet
# ─────────────────────────────────────────────────────────────────────────────

class TimetableEntryViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    Main CRUD for timetable entries plus specialised read endpoints.
    Write endpoints return expanded read data + optional warning.
    """
    permission_classes = [IsAuthenticated]

    # ── serializer routing ────────────────────────────────────────────────────

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PUT', 'PATCH'):
            return TimetableEntryWriteSerializer
        return TimetableEntryReadSerializer

    # ── default queryset (all entries for tenant, optional ?term= filter) ────

    def get_queryset(self):
        qs   = _base_entry_qs(self.school)
        term = self.request.query_params.get('term')
        if term:
            qs = qs.filter(term_id=term)
        return qs

    # ── write responses: return expanded data + surface warning ──────────────

    def _write_response(self, serializer, http_status):
        """
        Shared helper for create/update:
          1. Pull warning before save strips it.
          2. Save instance.
          3. Return read-serialised instance + optional warning.
        """
        warning  = serializer.validated_data.get('_warning')
        instance = serializer.save()

        read_data = TimetableEntryReadSerializer(
            instance, context=self.get_serializer_context()
        ).data

        if warning:
            read_data['warning'] = warning

        return Response(read_data, status=http_status)

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        return self._write_response(s, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial  = kwargs.pop('partial', False)
        instance = self.get_object()
        s = self.get_serializer(instance, data=request.data, partial=partial)
        s.is_valid(raise_exception=True)
        return self._write_response(s, status.HTTP_200_OK)

    # ── custom read actions ───────────────────────────────────────────────────

    @action(detail=False, url_path=r'by-class/(?P<class_arm_id>\d+)', methods=['get'])
    def by_class(self, request, class_arm_id=None):
        """All timetable entries for a specific class arm."""
        qs = self.get_queryset().filter(class_arm_id=class_arm_id)
        return Response(TimetableEntryReadSerializer(qs, many=True).data)

    @action(detail=False, url_path=r'by-teacher/(?P<teacher_id>\d+)', methods=['get'])
    def by_teacher(self, request, teacher_id=None):
        """All timetable entries for a specific teacher."""
        qs = self.get_queryset().filter(teacher_id=teacher_id)
        return Response(TimetableEntryReadSerializer(qs, many=True).data)

    @action(detail=False, url_path='my-timetable', methods=['get'])
    def my_timetable(self, request):
        """Logged-in teacher's own timetable."""
        if getattr(request.user, 'role', None) != 'teacher':
            return Response(
                {'detail': 'Only teachers can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = self.get_queryset().filter(teacher=request.user)
        return Response(TimetableEntryReadSerializer(qs, many=True).data)

    @action(detail=False, url_path='grid', methods=['get'])
    def grid(self, request):
        """
        One-shot payload for the TimetableBuilder grid.
        Returns both the ordered periods list AND the entries for
        the requested class_arm + term, so the frontend builds the
        grid entirely on the client side.

        Query params: class_arm (required), term (required)
        """
        class_arm_id = request.query_params.get('class_arm')
        term_id      = request.query_params.get('term')

        if not (class_arm_id and term_id):
            return Response(
                {'detail': 'Both class_arm and term query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        periods = Period.objects.filter(school=self.school).order_by('order_index')
        entries = (
            _base_entry_qs(self.school)
            .filter(class_arm_id=class_arm_id, term_id=term_id)
        )

        return Response({
            'periods': PeriodSerializer(periods, many=True).data,
            'entries': TimetableEntryReadSerializer(entries, many=True).data,
        })

    @action(detail=False, url_path='teacher-load', methods=['get'])
    def teacher_load(self, request):
        """
        Returns period counts per day for a teacher within a term.
        Used by the frontend to warn before assigning a potentially
        overloaded day (before the user actually clicks Save).

        Query params: teacher (required), term (required)
        Response:  { "MON": 3, "TUE": 5, ... }
        """
        teacher_id = request.query_params.get('teacher')
        term_id    = request.query_params.get('term')

        if not (teacher_id and term_id):
            return Response(
                {'detail': 'Both teacher and term query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django.db.models import Count
        rows = (
            TimetableEntry.objects
            .filter(school=self.school, teacher_id=teacher_id, term_id=term_id)
            .values('day_of_week')
            .annotate(count=Count('id'))
        )
        return Response({r['day_of_week']: r['count'] for r in rows})