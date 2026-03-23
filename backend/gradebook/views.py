"""
backend/gradebook/views.py

Gradebook ViewSet + domain endpoints.

Endpoint map (all under /api/gradebook/):
  GET    entries/?class_arm=&subject=&term=         spreadsheet rows
  POST   entries/bulk-update/                        save all rows in one call
  POST   entries/publish/?class_arm=&subject=&term= flip is_published
  GET    entries/grade-scale/                        school's grading bands

  GET    affective/?class_arm=&term=                 all affective rows for class
  PUT    affective/{student_id}/{term_id}/            upsert affective ratings

  GET    psychomotor/?class_arm=&term=               all psychomotor rows for class
  PUT    psychomotor/{student_id}/{term_id}/          upsert psychomotor ratings
"""

from decimal import Decimal

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets

from tenants.mixins import TenantMixin   # patched → tenants.mixins per project convention
from .models import (
    GradeScale, ScoreEntry,
    AffectiveDomain, PsychomotorDomain,
)
from .serializers import (
    GradeScaleSerializer,
    ScoreEntryReadSerializer,
    ScoreEntryWriteSerializer,
    BulkScoreUpdateSerializer,
    AffectiveDomainSerializer,
    PsychomotorDomainSerializer,
    AFFECTIVE_FIELDS, PSYCHOMOTOR_FIELDS,
    CA_MAXIMA, MAX_CA_TOTAL, MAX_EXAM,
)


# ─────────────────────────────────────────────────────────────────────────────
# Score Entry ViewSet
# ─────────────────────────────────────────────────────────────────────────────

class ScoreEntryViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names  = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PATCH'):
            return ScoreEntryWriteSerializer
        return ScoreEntryReadSerializer

    def get_queryset(self):
        qs = (
            ScoreEntry.objects
            .filter(school=self.school)
            .select_related('student', 'subject', 'class_arm', 'term', 'session')
        )
        p = self.request.query_params
        if p.get('class_arm'): qs = qs.filter(class_arm_id=p['class_arm'])
        if p.get('subject'):   qs = qs.filter(subject_id=p['subject'])
        if p.get('term'):      qs = qs.filter(term_id=p['term'])
        if p.get('session'):   qs = qs.filter(session_id=p['session'])
        return qs

    # ── GET grade-scale ───────────────────────────────────────────────────────

    @action(detail=False, url_path='grade-scale', methods=['get'])
    def grade_scale(self, request):
        """Return this school's grading bands + CA/exam maxima for the UI."""
        bands = GradeScale.objects.filter(school=self.school).order_by('-min_score')
        return Response({
            'bands':       GradeScaleSerializer(bands, many=True).data,
            'ca_maxima':   CA_MAXIMA,
            'max_ca':      MAX_CA_TOTAL,
            'max_exam':    MAX_EXAM,
        })

    # ── POST bulk-update/ ─────────────────────────────────────────────────────

    @action(detail=False, url_path='bulk-update', methods=['post'])
    @transaction.atomic
    def bulk_update(self, request):
        """
        Upsert an entire class × subject × term score sheet in one call.
        Body: { class_arm, subject, term, session, scores: [{student_id, ...}] }
        Returns the updated rows in read format.
        """
        ser = BulkScoreUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        school    = self.school
        class_arm_id = d['class_arm']
        subject_id   = d['subject']
        term_id      = d['term']
        session_id   = d['session']

        updated_ids = []
        errors      = {}

        for item in d['scores']:
            sid = item['student_id']

            # Per-row CA validation
            ca_sum = sum(item.get(f, Decimal('0')) or Decimal('0') for f in CA_MAXIMA)
            row_errors = {}

            for field, max_val in CA_MAXIMA.items():
                val = item.get(field, Decimal('0')) or Decimal('0')
                if val > max_val:
                    row_errors[field] = f'Max {max_val}'

            if ca_sum > MAX_CA_TOTAL:
                row_errors['ca_total'] = f'CA {ca_sum} > {MAX_CA_TOTAL}'

            exam = item.get('exam_score', Decimal('0')) or Decimal('0')
            if exam > MAX_EXAM:
                row_errors['exam_score'] = f'Max {MAX_EXAM}'

            if row_errors:
                errors[sid] = row_errors
                continue

            entry, _ = ScoreEntry.objects.update_or_create(
                school=school,
                student_id=sid,
                subject_id=subject_id,
                class_arm_id=class_arm_id,
                term_id=term_id,
                session_id=session_id,
                defaults={
                    'teacher':     request.user,
                    'first_test':  item.get('first_test',  Decimal('0')),
                    'second_test': item.get('second_test', Decimal('0')),
                    'assignment':  item.get('assignment',  Decimal('0')),
                    'project':     item.get('project',     Decimal('0')),
                    'practical':   item.get('practical',   Decimal('0')),
                    'exam_score':  item.get('exam_score',  Decimal('0')),
                },
            )
            updated_ids.append(entry.id)

        rows = ScoreEntry.objects.filter(id__in=updated_ids).select_related(
            'student', 'subject', 'class_arm', 'term', 'session'
        )
        return Response({
            'updated': ScoreEntryReadSerializer(rows, many=True).data,
            'errors':  errors,
        })

    # ── POST publish/ ─────────────────────────────────────────────────────────

    @action(detail=False, url_path='publish', methods=['post'])
    def publish(self, request):
        """
        Flip is_published=True for every entry in the class×subject×term.
        Requires class_arm, subject, term as query params.
        """
        p = request.query_params
        if not (p.get('class_arm') and p.get('subject') and p.get('term')):
            return Response(
                {'detail': 'class_arm, subject and term params required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        count = ScoreEntry.objects.filter(
            school=self.school,
            class_arm_id=p['class_arm'],
            subject_id=p['subject'],
            term_id=p['term'],
            is_published=False,
        ).update(is_published=True)

        return Response({'published': count})


# ─────────────────────────────────────────────────────────────────────────────
# Affective Domain
# ─────────────────────────────────────────────────────────────────────────────

class AffectiveDomainViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = AffectiveDomainSerializer

    def get_queryset(self):
        qs = AffectiveDomain.objects.filter(school=self.school).select_related('student')
        p  = self.request.query_params
        if p.get('class_arm'): qs = qs.filter(class_arm_id=p['class_arm'])
        if p.get('term'):      qs = qs.filter(term_id=p['term'])
        return qs

    @action(
        detail=False,
        url_path=r'student/(?P<student_id>\d+)/term/(?P<term_id>\d+)',
        methods=['get', 'put'],
    )
    def student_term(self, request, student_id=None, term_id=None):
        """GET or upsert affective ratings for one student in one term."""
        instance, _ = AffectiveDomain.objects.get_or_create(
            school=self.school,
            student_id=student_id,
            term_id=term_id,
            defaults={'class_arm_id': request.data.get('class_arm')},
        )
        if request.method == 'PUT':
            ser = AffectiveDomainSerializer(
                instance, data=request.data, partial=True,
                context=self.get_serializer_context()
            )
            ser.is_valid(raise_exception=True)
            ser.save()
            instance.refresh_from_db()

        return Response(AffectiveDomainSerializer(instance).data)


# ─────────────────────────────────────────────────────────────────────────────
# Psychomotor Domain
# ─────────────────────────────────────────────────────────────────────────────

class PsychomotorDomainViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class   = PsychomotorDomainSerializer

    def get_queryset(self):
        qs = PsychomotorDomain.objects.filter(school=self.school).select_related('student')
        p  = self.request.query_params
        if p.get('class_arm'): qs = qs.filter(class_arm_id=p['class_arm'])
        if p.get('term'):      qs = qs.filter(term_id=p['term'])
        return qs

    @action(
        detail=False,
        url_path=r'student/(?P<student_id>\d+)/term/(?P<term_id>\d+)',
        methods=['get', 'put'],
    )
    def student_term(self, request, student_id=None, term_id=None):
        """GET or upsert psychomotor ratings for one student in one term."""
        instance, _ = PsychomotorDomain.objects.get_or_create(
            school=self.school,
            student_id=student_id,
            term_id=term_id,
            defaults={'class_arm_id': request.data.get('class_arm')},
        )
        if request.method == 'PUT':
            ser = PsychomotorDomainSerializer(
                instance, data=request.data, partial=True,
                context=self.get_serializer_context()
            )
            ser.is_valid(raise_exception=True)
            ser.save()
            instance.refresh_from_db()

        return Response(PsychomotorDomainSerializer(instance).data)