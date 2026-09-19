from django.db import transaction
from datetime import timedelta
from copy import deepcopy
from .services import session_questions
from accounts.school_access import SchoolModulePermission, require_assignment
"""
backend/cbt/views.py

Endpoint map:
  GET/POST              /api/cbt/topics/                        â†’ TopicViewSet
  GET/POST              /api/cbt/questions/                     â†’ QuestionViewSet
  GET                   /api/cbt/questions/stats/               â†’ question counts
  POST                  /api/cbt/questions/bulk-import/         â†’ JSON array import
  GET/POST              /api/cbt/exams/                         â†’ CBTExamViewSet
  GET                   /api/cbt/exams/available/               â†’ student's upcoming exams
  POST                  /api/cbt/exams/{id}/start/              â†’ begin exam, get questions
  POST                  /api/cbt/exams/{id}/save-answer/        â†’ auto-save one answer
  GET                   /api/cbt/exams/{id}/status/             â†’ time + saved answers
  POST                  /api/cbt/exams/{id}/submit/             â†’ final submission + scoring
  POST                  /api/cbt/exams/{id}/log-tab-switch/     â†’ increment tab switch counter
  POST                  /api/cbt/exams/{id}/push-to-gradebook/  â†’ write scores to ScoreEntry
  GET                   /api/cbt/exams/{id}/review/             â†’ student post-exam review
  GET                   /api/cbt/exams/{id}/results/            â†’ admin per-student table
  GET                   /api/cbt/exams/{id}/question-analysis/  â†’ per-question stats
"""

import random
from collections import Counter
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.permissions import IsSchoolAdminOrTeacher
from tenants.mixins import TenantMixin
from .models import Topic, Question, CBTExam, StudentExamSession, StudentAnswer
from .serializers import (
    TopicSerializer, QuestionSerializer, QuestionWriteSerializer,
    CBTExamListSerializer, CBTExamWriteSerializer,
    ExamQuestionSerializer, ExamSessionStatusSerializer,
)
from .services import auto_mark


class TopicViewSet(TenantMixin, ModelViewSet):
    serializer_class   = TopicSerializer
    permission_classes = [SchoolModulePermission]

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
    permission_classes = [SchoolModulePermission]

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

    @action(detail=False, methods=['get'], url_path='docx-template', permission_classes=[IsSchoolAdminOrTeacher])
    def docx_template(self, request):
        from django.http import HttpResponse
        from .docx_import import question_template
        response = HttpResponse(question_template(), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        response['Content-Disposition'] = 'attachment; filename="questions-template.docx"'
        return response

    @action(detail=False, methods=['post'], url_path='docx-preview', permission_classes=[IsSchoolAdminOrTeacher])
    def docx_preview(self, request):
        from .docx_import import parse_questions
        upload = request.FILES.get('file')
        if not upload:
            return Response({'detail': 'Choose a Word .docx file.'}, status=400)
        try:
            return Response({'questions': parse_questions(upload)})
        except ValueError as error:
            return Response({'detail': str(error)}, status=400)

    @action(detail=False, methods=['post'], url_path='bulk-import', permission_classes=[IsSchoolAdminOrTeacher])
    def bulk_import(self, request):
        """
        Import a JSON array of question objects.
        Each item must match QuestionWriteSerializer fields.
        Returns {imported: N, errors: [{index, detail}]}.
        """
        items = request.data
        if not isinstance(items, list) or not 1 <= len(items) <= 200:
            return Response({'detail': 'Expected an array of 1 to 200 questions.'}, status=400)

        imported = 0
        errors   = []

        for i, item in enumerate(items):
            ser = QuestionWriteSerializer(data=item, context=self.get_serializer_context())
            if ser.is_valid():
                ser.save(school=self.school, created_by=request.user)
                imported += 1
            else:
                errors.append({'index': i, 'detail': ser.errors})

        return Response(
            {'imported': imported, 'errors': errors},
            status=status.HTTP_207_MULTI_STATUS if errors else status.HTTP_201_CREATED,
        )


# â”€â”€ CBT Exam ViewSet â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class CBTExamViewSet(TenantMixin, ModelViewSet):
    permission_classes = [SchoolModulePermission]

    @action(detail=True, methods=['get'], permission_classes=[IsSchoolAdminOrTeacher])
    def configuration(self, request, pk=None):
        return Response(CBTExamWriteSerializer(self.get_object(), context=self.get_serializer_context()).data)

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return CBTExamWriteSerializer
        return CBTExamListSerializer

    def get_queryset(self):
        return CBTExam.objects.filter(school=self.school).prefetch_related('class_arms')

    def perform_create(self, serializer):
        serializer.save(school=self.school, created_by=self.request.user)

    # â”€â”€ /exams/available/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=False, methods=['get'])
    def available(self, request):
        """
        Returns exams available to the logged-in student:
          - published or ongoing
          - the student's class arm is listed on the exam
          - not already submitted/timed-out
        """
        user = request.user
        now  = timezone.now()

        # Find the student's current class arm
        try:
            arm = user.student_profile.current_class
        except Exception:
            return Response([])

        exams = list(CBTExam.objects.filter(
            school=self.school,
            status__in=['published', 'ongoing'],
            class_arms=arm,
        ).prefetch_related('class_arms'))

        # Batch-fetch all sessions for these exams in one query
        sessions_map = {
            s.exam_id: s
            for s in StudentExamSession.objects.filter(exam__in=exams, student=user)
        }

        result = []
        for exam in exams:
            session = sessions_map.get(exam.id)
            item = CBTExamListSerializer(exam).data
            item['session_status'] = session.status if session else None
            item['score']          = float(session.score) if exam.show_score_immediately and session and session.score is not None else None
            result.append(item)

        return Response(result)

    # â”€â”€ /exams/{id}/start/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def start(self, request, pk=None):
        """
        Begin the exam for the current student.
        - Creates (or resumes) a StudentExamSession
        - Shuffles question order and option positions
        - Returns the question list (NO correct_answer field)
        """
        exam = self.get_object()
        user = request.user
        now  = timezone.now()

        if user.role != 'student' or user.school_id != exam.school_id or not exam.class_arms.filter(pk=getattr(getattr(user, 'student_profile', None), 'current_class_id', None)).exists():
            return Response({'detail': 'You are not assigned to this exam.'}, status=403)
        if now < exam.start_datetime or now >= exam.end_datetime:
            return Response({'detail': 'This exam is outside its scheduled time.'}, status=400)
        exam = CBTExam.objects.select_for_update().get(pk=exam.pk)
        if exam.status not in ('published', 'ongoing'):
            return Response({'detail': 'This exam is not available.'}, status=400)

        session, created = StudentExamSession.objects.get_or_create(
            exam=exam, student=user,
            defaults={'ip_address': _get_client_ip(request)},
        )

        if session.status in ('submitted', 'timed_out'):
            return Response({'detail': 'You have already completed this exam.'}, status=400)

        if created or session.status == 'not_started':
            questions = exam.resolve_questions()
            requested_count = sum(rule.get('count', 0) for rule in exam.random_config) if exam.selection_mode != 'manual' else len(questions)
            if not questions or len(questions) != requested_count:
                return Response({'detail':'The exam does not have enough active questions. Contact your teacher.'}, status=400)
            session.question_snapshot = [QuestionSerializer(q).data for q in questions]
            session.deadline_at = min(exam.end_datetime, now + timedelta(minutes=exam.duration_minutes))

            option_maps = {}
            if exam.randomize_options:
                for q in questions:
                    if q.question_type in ('mcq', 'true_false') and q.options:
                        ids = [o['id'] for o in q.options]
                        shuffled = ids[:]
                        random.shuffle(shuffled)
                        option_maps[str(q.id)] = dict(zip(ids, shuffled))

            session.question_order = [q.id for q in questions]
            session.option_maps    = option_maps
            session.status         = 'in_progress'
            session.started_at     = now
            session.time_remaining_seconds = max(0, int((session.deadline_at - now).total_seconds()))
            session.save()

            # Mark exam ongoing if it's still in published state
            if exam.status == 'published':
                CBTExam.objects.filter(pk=exam.pk).update(status='ongoing')
        else:
            if _finalize_if_expired(session, exam, now):
                return Response({'detail': 'Exam time has expired.'}, status=400)
            session.time_remaining_seconds = _remaining_seconds(session, exam, now)
            session.save(update_fields=['time_remaining_seconds'])

        questions = _build_question_list(session)
        return Response({
            'session_id':           session.id,
            'time_remaining_seconds': session.time_remaining_seconds,
            'allow_review':         exam.allow_review,
            'questions':            questions,
        })

    # â”€â”€ /exams/{id}/save-answer/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['post'], url_path='save-answer')
    @transaction.atomic
    def save_answer(self, request, pk=None):
        """
        Auto-save a single answer.
        Body: {question_id, selected_option, time_spent_seconds?}
        """
        exam    = self.get_object()
        user    = request.user
        try:
            q_id = int(request.data.get('question_id', 0))
        except (TypeError, ValueError):
            return Response({'detail': 'question_id must be an integer.'}, status=400)
        option  = request.data.get('selected_option', '')
        try:
            spent = max(0, int(request.data.get('time_spent_seconds', 0)))
        except (TypeError, ValueError):
            return Response({'detail':'Invalid time spent.'}, status=400)
        if not isinstance(option, str) or len(option) > 1000:
            return Response({'detail':'Invalid answer.'}, status=400)

        session = _get_active_session(exam, user)
        if isinstance(session, Response):
            return session

        # Verify the question belongs to this session
        if q_id not in session.question_order:
            return Response({'detail': 'Question not in this exam.'}, status=400)

        StudentAnswer.objects.update_or_create(
            exam_session=session,
            question_id=q_id,
            defaults={'selected_option': option, 'time_spent_seconds': spent},
        )
        return Response({'saved': True})

    # â”€â”€ /exams/{id}/status/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['get'])
    @transaction.atomic
    def status(self, request, pk=None):
        """Return remaining time and all saved answers for the student's session."""
        exam    = self.get_object()
        user    = request.user
        session = StudentExamSession.objects.filter(exam=exam, student=user).first()
        if not session:
            return Response({'detail': 'No session found.'}, status=404)

        # Recalculate against the persisted deadline, not the mutable exam duration.
        if session.status == 'in_progress':
            now = timezone.now()
            if _finalize_if_expired(session, exam, now):
                session.refresh_from_db()
            else:
                session.time_remaining_seconds = _remaining_seconds(session, exam, now)
                session.save(update_fields=['time_remaining_seconds'])

        payload = ExamSessionStatusSerializer(session).data
        if not exam.show_score_immediately:
            payload['score'] = None
        return Response(payload)

    # â”€â”€ /exams/{id}/submit/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def submit(self, request, pk=None):
        """
        Final submission â€” marks all answers, computes percentage score.
        """
        exam    = self.get_object()
        user    = request.user
        session = _get_active_session(exam, user)
        if isinstance(session, Response):
            return session

        auto_mark(session, final_status='submitted')

        payload = {'score': float(session.score) if exam.show_score_immediately else None, 'status': 'submitted'}
        if exam.show_score_immediately:
            payload['answers'] = list(
                session.answers.values('question_id', 'selected_option', 'is_correct')
            )
        return Response(payload)

    # â”€â”€ /exams/{id}/log-tab-switch/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['post'], url_path='log-tab-switch')
    @transaction.atomic
    def log_tab_switch(self, request, pk=None):
        """Increment tab_switch_count for the student's active session."""
        exam    = self.get_object()
        session = StudentExamSession.objects.filter(
            exam=exam, student=request.user, status='in_progress'
        ).first()
        if session:
            session.tab_switch_count += 1
            session.save(update_fields=['tab_switch_count'])
        return Response({'tab_switch_count': session.tab_switch_count if session else 0})

    # â”€â”€ /exams/{id}/push-to-gradebook/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['post'], url_path='push-to-gradebook',
            permission_classes=[IsSchoolAdminOrTeacher])
    def push_to_gradebook(self, request, pk=None):
        """
        Scale every completed session's CBT percentage to the subject's
        max_exam_score and upsert a ScoreEntry.exam_score.

        Returns {updated: N, skipped: N}.
        """
        from gradebook.models import ScoreEntry

        exam = self.get_object()
        sessions = StudentExamSession.objects.filter(
            exam=exam, status__in=['submitted', 'timed_out']
        ).select_related('student', 'student__student_profile')

        max_exam = exam.subject.max_exam_score
        updated  = 0
        skipped  = 0

        for sess in sessions:
            try:
                profile   = sess.student.student_profile
                class_arm = profile.current_class
                if not class_arm:
                    skipped += 1
                    continue

                scaled = (
                    Decimal(str(sess.score)) / Decimal('100') * Decimal(str(max_exam))
                ).quantize(Decimal('0.01'))

                ScoreEntry.objects.update_or_create(
                    student  = sess.student,
                    subject  = exam.subject,
                    term     = exam.term,
                    session  = exam.session,
                    school   = exam.school,
                    defaults = {
                        'class_arm':  class_arm,
                        'exam_score': scaled,
                    },
                )
                updated += 1
            except Exception:
                skipped += 1

        return Response({'updated': updated, 'skipped': skipped})

    # â”€â”€ /exams/{id}/review/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['get'])
    def review(self, request, pk=None):
        """
        Post-exam review for the student â€” questions with their answer,
        the correct answer, and the explanation.
        Only available after submission and only if allow_review=True.
        """
        exam    = self.get_object()
        user    = request.user
        session = StudentExamSession.objects.filter(exam=exam, student=user).first()

        if not session or session.status not in ('submitted', 'timed_out'):
            return Response({'detail': 'Review not available yet.'}, status=403)

        if not exam.allow_review or timezone.now() < exam.end_datetime:
            return Response({'detail': 'Review is disabled for this exam.'}, status=403)

        answers = {a.question_id: a for a in session.answers.select_related('question')}
        q_map = session_questions(session)

        result = []
        for q_id in session.question_order:
            q   = q_map.get(q_id)
            ans = answers.get(q_id)
            if not q:
                continue

            # Re-apply shuffle for display consistency
            omap      = session.option_maps.get(str(q_id), {})
            rev_map   = {v: k for k, v in omap.items()}
            options   = _shuffled_options(q, omap)

            # What the student picked (in shuffled space) and the correct (in original space)
            selected  = ans.selected_option if ans else ''
            # Map correct_answer to shuffled space for display
            correct_shuffled = omap.get(q.correct_answer, q.correct_answer)

            result.append({
                'id':               q.id,
                'question_text':    q.question_text,
                'question_image':   q.question_image,
                'question_type':    q.question_type,
                'options':          options,
                'selected_option':  selected,
                'correct_option':   correct_shuffled,
                'is_correct':       ans.is_correct if ans else None,
                'explanation':      q.explanation,
            })

        return Response({
            'score':     float(session.score),
            'questions': result,
        })

    # â”€â”€ /exams/{id}/results/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['get'], permission_classes=[IsSchoolAdminOrTeacher])
    def results(self, request, pk=None):
        """
        Admin / teacher view: per-student performance table.
        Returns [{student_id, name, score, time_taken_seconds, tab_switches, status}].
        """
        exam     = self.get_object()
        sessions = (
            StudentExamSession.objects
            .filter(exam=exam)
            .select_related('student')
            .order_by('-score')
        )

        data = []
        for sess in sessions:
            time_taken = None
            if sess.started_at and sess.submitted_at:
                time_taken = int((sess.submitted_at - sess.started_at).total_seconds())

            data.append({
                'student_id':        sess.student_id,
                'name':              sess.student.get_full_name() or sess.student.email,
                'score':             float(sess.score) if sess.score is not None else None,
                'status':            sess.status,
                'time_taken_seconds': time_taken,
                'tab_switches':      sess.tab_switch_count,
            })

        return Response({
            'exam_title':     exam.title,
            'total_students': len(data),
            'results':        data,
        })

    # â”€â”€ /exams/{id}/question-analysis/ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    @action(detail=True, methods=['get'], url_path='question-analysis',
            permission_classes=[IsSchoolAdminOrTeacher])
    def question_analysis(self, request, pk=None):
        """
        Per-question analysis: % answered correctly and most common wrong option.
        """
        exam = self.get_object()

        # Collect all answer rows for this exam
        answers = (
            StudentAnswer.objects
            .filter(exam_session__exam=exam)
            .select_related('question')
        )

        # Group by question
        from collections import defaultdict
        q_data: dict = defaultdict(lambda: {'correct': 0, 'total': 0, 'wrong_opts': []})
        for ans in answers:
            q_data[ans.question_id]['total'] += 1
            if ans.is_correct:
                q_data[ans.question_id]['correct'] += 1
            elif ans.selected_option:
                q_data[ans.question_id]['wrong_opts'].append(ans.selected_option)

        q_map = {
            q.id: q
            for q in Question.objects.filter(id__in=list(q_data.keys()))
        }

        result = []
        for q_id, stats in q_data.items():
            q     = q_map.get(q_id)
            total = stats['total']
            pct   = round(stats['correct'] / total * 100, 1) if total else 0

            most_wrong = None
            if stats['wrong_opts']:
                most_wrong = Counter(stats['wrong_opts']).most_common(1)[0][0]

            result.append({
                'question_id':        q_id,
                'question_text':      q.question_text if q else '',
                'total_answered':     total,
                'correct_count':      stats['correct'],
                'pct_correct':        pct,
                'most_chosen_wrong':  most_wrong,
            })

        result.sort(key=lambda x: x['pct_correct'])
        return Response(result)


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _session_deadline(session, exam):
    if session.deadline_at:
        return session.deadline_at
    if session.started_at:
        return min(exam.end_datetime, session.started_at + timedelta(minutes=exam.duration_minutes))
    return None


def _remaining_seconds(session, exam, now=None):
    deadline = _session_deadline(session, exam)
    if not deadline:
        return 0
    now = now or timezone.now()
    return max(0, int((deadline - now).total_seconds()))


def _finalize_if_expired(session, exam, now=None):
    deadline = _session_deadline(session, exam)
    now = now or timezone.now()
    if not deadline or now >= deadline:
        auto_mark(session, final_status='timed_out')
        session.time_remaining_seconds = 0
        session.save(update_fields=['time_remaining_seconds'])
        return True
    return False


def _get_active_session(exam, user):
    """Return the in-progress session or a Response error."""
    session = StudentExamSession.objects.select_for_update().filter(exam=exam, student=user).first()
    if not session:
        return Response({'detail': 'No session found. Call /start/ first.'}, status=404)
    if session.status in ('submitted', 'timed_out'):
        return Response({'detail': 'Exam already completed.'}, status=400)
    if _finalize_if_expired(session, exam):
        return Response({'detail':'Exam time has expired.'}, status=400)
    return session


def _build_question_list(session):
    """
    Return questions in session order with options shuffled per option_maps.
    correct_answer is NOT included.
    """
    q_map = session_questions(session)
    result = []
    for q_id in session.question_order:
        q = q_map.get(q_id)
        if not q:
            continue
        data = deepcopy({name: getattr(q, name) for name in ('id','question_text','question_image','question_type','options')})
        # Apply option shuffle map
        omap = session.option_maps.get(str(q_id))
        if omap and data.get('options'):
            for opt in data['options']:
                opt['id'] = omap.get(opt['id'], opt['id'])
            data['options'].sort(key=lambda o: o['id'])
        result.append(data)
    return result


def _shuffled_options(question, omap):
    """Return question options with ids remapped through omap (for review display)."""
    opts = []
    for opt in question.options:
        opts.append({
            'id':   omap.get(opt['id'], opt['id']),
            'text': opt['text'],
        })
    opts.sort(key=lambda o: o['id'])
    return opts


