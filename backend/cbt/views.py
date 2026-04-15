"""
backend/cbt/views.py

Endpoint map:
  GET/POST   /api/cbt/topics/                         → TopicViewSet
  GET/POST   /api/cbt/questions/                      → QuestionViewSet list/create
  GET/PUT/PATCH/DELETE /api/cbt/questions/{id}/       → QuestionViewSet detail
  GET        /api/cbt/questions/stats/                → question counts by subject/difficulty
  POST       /api/cbt/questions/bulk-import/          → JSON array import
"""

from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from tenants.mixins import TenantMixin
from .models import Topic, Question
from .serializers import TopicSerializer, QuestionSerializer, QuestionWriteSerializer


class TopicViewSet(TenantMixin, ModelViewSet):
    serializer_class   = TopicSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Topic.objects.filter(school=self.school).select_related('subject', 'class_level')
        subject = self.request.query_params.get('subject')
        level   = self.request.query_params.get('class_level')
        if subject:
            qs = qs.filter(subject_id=subject)
        if level:
            qs = qs.filter(class_level_id=level)
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.school)


class QuestionViewSet(TenantMixin, ModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return QuestionWriteSerializer
        return QuestionSerializer

    def get_queryset(self):
        qs = Question.objects.filter(school=self.school).select_related(
            'subject', 'topic', 'class_level'
        )
        # Filters
        subject     = self.request.query_params.get('subject')
        topic       = self.request.query_params.get('topic')
        difficulty  = self.request.query_params.get('difficulty')
        level       = self.request.query_params.get('class_level')
        q_type      = self.request.query_params.get('question_type')
        is_active   = self.request.query_params.get('is_active')
        search      = self.request.query_params.get('search')

        if subject:
            qs = qs.filter(subject_id=subject)
        if topic:
            qs = qs.filter(topic_id=topic)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        if level:
            qs = qs.filter(class_level_id=level)
        if q_type:
            qs = qs.filter(question_type=q_type)
        if is_active is not None:
            qs = qs.filter(is_active=(is_active.lower() == 'true'))
        if search:
            qs = qs.filter(question_text__icontains=search)

        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.school, created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(school=self.school)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Returns question counts grouped by subject and difficulty.
        Response shape:
          {
            total: N,
            by_subject: [{subject_id, subject_name, count}, ...],
            by_difficulty: {easy: N, medium: N, hard: N},
            by_type: {mcq: N, true_false: N, fill_blank: N},
          }
        """
        base_qs = Question.objects.filter(school=self.school, is_active=True)

        by_subject = list(
            base_qs
            .values('subject__id', 'subject__name')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        by_difficulty = {
            row['difficulty']: row['count']
            for row in base_qs.values('difficulty').annotate(count=Count('id'))
        }

        by_type = {
            row['question_type']: row['count']
            for row in base_qs.values('question_type').annotate(count=Count('id'))
        }

        return Response({
            'total':         base_qs.count(),
            'by_subject':    [
                {'subject_id': r['subject__id'], 'subject_name': r['subject__name'], 'count': r['count']}
                for r in by_subject
            ],
            'by_difficulty': by_difficulty,
            'by_type':       by_type,
        })

    @action(detail=False, methods=['post'])
    def bulk_import(self, request):
        """
        Import a JSON array of question objects.
        Each item must match QuestionWriteSerializer fields.
        Returns {imported: N, errors: [{index, detail}]}.
        """
        items = request.data
        if not isinstance(items, list):
            return Response({'detail': 'Expected a JSON array.'}, status=400)

        imported = 0
        errors   = []

        for i, item in enumerate(items):
            ser = QuestionWriteSerializer(data=item)
            if ser.is_valid():
                ser.save(school=self.school, created_by=request.user)
                imported += 1
            else:
                errors.append({'index': i, 'detail': ser.errors})

        return Response(
            {'imported': imported, 'errors': errors},
            status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED,
        )
