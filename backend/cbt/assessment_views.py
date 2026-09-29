"""Premium paper and online assignment workflows within the existing CBT domain."""
import random
from urllib.parse import urlsplit
from decimal import Decimal, ROUND_HALF_UP
from html import escape

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.school_access import SchoolModulePermission, require_assignment
from tenants.mixins import TenantMixin
from .assessment_serializers import ModeSerializer, PaperSerializer, AssignmentSerializer
from .gradebook import integrate_component
from .models import SubjectAssessmentMode, ExamPaper, OnlineAssignment, AssignmentSubmission, Question
from .serializers import QuestionSerializer


def approved_image(url):
    """Only render school-uploaded Cloudinary images in a server-side PDF."""
    if not url:
        return ''
    parsed = urlsplit(str(url))
    cloud = settings.CLOUDINARY_STORAGE.get('CLOUD_NAME', '')
    return escape(str(url), quote=True) if (cloud and parsed.scheme == 'https' and
        parsed.netloc == 'res.cloudinary.com' and parsed.path.startswith(f'/{cloud}/image/upload/')) else ''


class SubjectAssessmentModeViewSet(TenantMixin, ModelViewSet):
    serializer_class = ModeSerializer
    permission_classes = [SchoolModulePermission]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return SubjectAssessmentMode.objects.filter(school=self.school).order_by('pk')

    def perform_create(self, serializer):
        if self.request.user.role != 'school_admin':
            raise PermissionDenied('Only school administrators select assessment mode.')
        serializer.save(school=self.school)

    def perform_update(self, serializer):
        if self.request.user.role != 'school_admin':
            raise PermissionDenied('Only school administrators select assessment mode.')
        serializer.save()


class ExamPaperViewSet(TenantMixin, ModelViewSet):
    serializer_class = PaperSerializer
    permission_classes = [SchoolModulePermission]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = ExamPaper.objects.filter(school=self.school).select_related('term__session', 'subject', 'class_level').order_by('-created_at', '-pk')
        if self.request.user.role == 'teacher':
            from django.db.models import Exists, OuterRef
            from enrollment.models import SubjectAssignment
            assigned = SubjectAssignment.objects.filter(school=self.school,
                teacher__user=self.request.user, teacher__employment_status='active',
                subject_id=OuterRef('subject_id'), term_id=OuterRef('term_id'),
                class_arm__class_level_id=OuterRef('class_level_id'))
            qs = qs.filter(Exists(assigned))
        return qs

    def perform_create(self, serializer):
        serializer.save(school=self.school, created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def generate(self, request, pk=None):
        paper = ExamPaper.objects.select_for_update().get(pk=self.get_object().pk)
        if paper.status != 'draft':
            raise ValidationError('Only a draft paper can be generated.')
        if paper.question_snapshot:
            return Response(PaperSerializer(paper).data)
        selected = []
        for row in paper.blueprint:
            for kind, count in [('objective', row.get('objective', 0)), ('theory', row.get('theory', 0))]:
                if not count:
                    continue
                pool = Question.objects.filter(school=self.school, subject=paper.subject,
                    class_level=paper.class_level, curriculum_topic_id=row['topic_id'],
                    source='bank', is_active=True).exclude(pk__in=[item[0] for item in selected])
                pool = pool.filter(question_type='theory') if kind == 'theory' else pool.exclude(question_type='theory')
                ids = list(pool.values_list('id', flat=True))
                if len(ids) < count:
                    from curriculum.models import CurriculumTopic
                    topic = CurriculumTopic.objects.get(pk=row['topic_id'])
                    raise ValidationError(f'{topic.title} requires {count} {kind} questions; only {len(ids)} eligible questions exist.')
                selected.extend((question_id, kind, row['topic_id']) for question_id in random.sample(ids, count))
        questions = {q.id: q for q in Question.objects.filter(pk__in=[item[0] for item in selected])}
        paper.question_snapshot = [{**QuestionSerializer(questions[question_id]).data,
                                    'section': kind, 'blueprint_topic_id': topic_id}
                                   for question_id, kind, topic_id in selected]
        paper.save(update_fields=['question_snapshot'])
        return Response(PaperSerializer(paper).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def replace(self, request, pk=None):
        paper = ExamPaper.objects.select_for_update().get(pk=self.get_object().pk)
        if paper.status != 'draft' or not paper.question_snapshot:
            raise ValidationError('Only generated draft questions may be replaced.')
        try:
            index, question_id = int(request.data['index']), int(request.data['question_id'])
            old = paper.question_snapshot[index]
        except (KeyError, ValueError, TypeError, IndexError):
            raise ValidationError('Choose a valid paper position and replacement question.')
        new = get_object_or_404(Question, pk=question_id, school=self.school, subject=paper.subject,
                                class_level=paper.class_level, source='bank', is_active=True,
                                curriculum_topic_id=old['blueprint_topic_id'])
        if (new.question_type == 'theory') != (old['section'] == 'theory') or any(row['id'] == new.pk for row in paper.question_snapshot):
            raise ValidationError('Choose a distinct question from the same topic and section.')
        paper.question_snapshot[index] = {**QuestionSerializer(new).data,
                                          'section': old['section'], 'blueprint_topic_id': old['blueprint_topic_id']}
        paper.save(update_fields=['question_snapshot'])
        return Response(PaperSerializer(paper).data)

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def submit(self, request, pk=None):
        paper = ExamPaper.objects.select_for_update().get(pk=self.get_object().pk)
        if paper.status != 'draft' or not paper.question_snapshot:
            raise ValidationError('Generate and review a draft before submitting it.')
        paper.status = 'submitted'
        paper.save(update_fields=['status'])
        return Response({'status': paper.status})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def approve(self, request, pk=None):
        if request.user.role != 'school_admin':
            raise PermissionDenied('Only school administrators approve examination papers.')
        paper = ExamPaper.objects.select_for_update().get(pk=self.get_object().pk)
        if paper.status != 'submitted':
            raise ValidationError('Only a submitted paper may be approved.')
        paper.status, paper.approved_by, paper.approved_at = 'approved', request.user, timezone.now()
        paper.save(update_fields=['status', 'approved_by', 'approved_at'])
        return Response({'status': paper.status})

    @action(detail=True, methods=['get'])
    def pdf(self, request, pk=None):
        paper = self.get_object()
        if not paper.question_snapshot:
            raise ValidationError('Generate the paper before printing.')
        marking = request.query_params.get('marking') == '1'
        heading = '' if paper.status == 'approved' else '<div class="draft">DRAFT - NOT APPROVED FOR EXAMINATION</div>'
        rows = []
        for section, title in (('objective', 'Section A - Objective'), ('theory', 'Section B - Theory')):
            section_questions = [q for q in paper.question_snapshot if q['section'] == section]
            if not section_questions:
                continue
            rows.append(f'<h2 class="section-title">{title}</h2>')
            for number, q in enumerate(section_questions, 1):
                options = ''.join(f'<li>{escape(str(option.get("id", "")))}. {escape(str(option.get("text", "")))}'
                    + (f'<br><img class="option-image" src="{approved_image(option.get("image_url"))}">' if approved_image(option.get('image_url')) else '')
                    + '</li>' for option in q.get('options', []))
                answer = f'<p><b>Answer/marking guidance:</b> {escape(q.get("correct_answer", ""))} {escape(q.get("explanation", ""))}</p>' if marking else ''
                question_image = approved_image(q.get('question_image'))
                image = f'<img class="question-image" src="{question_image}">' if question_image else ''
                rows.append(f'<section><b>{number}. {escape(q["question_text"])} ({escape(str(q.get("marks", 1)))} marks)</b>{image}<ol>{options}</ol>{answer}</section>')
        school_logo = approved_image(paper.school.logo)
        logo = f'<img class="school-logo" src="{school_logo}" alt="">' if school_logo else ''
        html = f'''<!doctype html><html><head><meta charset="utf-8"><style>
            @page{{size:A4;margin:22mm 18mm;@bottom-center{{content:counter(page)}}}}
            body{{font-family:Arial,sans-serif;color:#14253d}}
            h1,h2{{text-align:center;margin:4px}} section{{break-inside:avoid;margin:18px 0}}
            .school-logo{{display:block;max-height:24mm;max-width:32mm;margin:0 auto 8px}}
            .question-image{{display:block;max-height:55mm;max-width:150mm;margin:8px 0}}
            .option-image{{max-height:24mm;max-width:45mm}} .section-title{{margin-top:22px}}
            .draft{{border:2px solid #a00;color:#a00;text-align:center;padding:10px;font-weight:bold}}
            .details{{text-align:center;border-bottom:1px solid #666;padding:10px}}
            </style></head><body>{heading}{logo}<h1>{escape(paper.school.name)}</h1>
            <h2>{escape(paper.title)}</h2><div class="details">{escape(paper.term.session.name)} | {escape(str(paper.term))} |
            {escape(paper.class_level.name)} | {escape(paper.subject.name)} | {paper.duration_minutes} minutes</div>
            <p>{escape(paper.instructions)}</p>{''.join(rows)}</body></html>'''
        from weasyprint import HTML
        data = HTML(string=html).write_pdf()
        response = HttpResponse(data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="paper-{paper.pk}{"-marking" if marking else ""}.pdf"'
        return response


class OnlineAssignmentViewSet(TenantMixin, ModelViewSet):
    serializer_class = AssignmentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_active or request.user.school_id != getattr(request.tenant, 'pk', None) or request.user.must_change_password:
            raise PermissionDenied('Select your school account.')
        if request.user.role not in ('school_admin', 'teacher', 'student'):
            raise PermissionDenied('This assignment is not available to your role.')

    def get_queryset(self):
        qs = OnlineAssignment.objects.filter(school=self.school).select_related('class_arm', 'term', 'subject').order_by('-created_at', '-pk')
        if self.request.user.role == 'student':
            arm_id = getattr(getattr(self.request.user, 'student_profile', None), 'current_class_id', None)
            return qs.filter(class_arm_id=arm_id, status__in=['published', 'closed'])
        if self.request.user.role == 'teacher':
            from django.db.models import Exists, OuterRef
            from enrollment.models import SubjectAssignment
            assigned = SubjectAssignment.objects.filter(school=self.school, teacher__user=self.request.user,
                teacher__employment_status='active', class_arm_id=OuterRef('class_arm_id'),
                subject_id=OuterRef('subject_id'), term_id=OuterRef('term_id'))
            return qs.filter(Exists(assigned))
        return qs

    def perform_create(self, serializer):
        if self.request.user.role == 'student':
            raise PermissionDenied('Students cannot create assignments.')
        serializer.save(school=self.school, created_by=self.request.user)

    def perform_update(self, serializer):
        if self.request.user.role == 'student':
            raise PermissionDenied('Students cannot edit assignments.')
        serializer.save()

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def publish(self, request, pk=None):
        if request.user.role == 'student':
            raise PermissionDenied('Students cannot publish assignments.')
        assignment = OnlineAssignment.objects.select_for_update().get(pk=self.get_object().pk)
        if assignment.status != 'draft' or assignment.due_at <= timezone.now():
            raise ValidationError('Publish a draft before its deadline.')
        assignment.status = 'published'
        assignment.save(update_fields=['status'])
        return Response({'status': assignment.status})

    @action(detail=True, methods=['post'], url_path='save-response')
    @transaction.atomic
    def save_response(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role != 'student':
            raise PermissionDenied('Only the assigned student can save a response.')
        if assignment.status != 'published' or timezone.now() >= assignment.due_at:
            raise ValidationError('This assignment is closed for submissions.')
        text = request.data.get('text', '')
        answers = request.data.get('answers', {})
        if not isinstance(text, str) or len(text) > 20000 or not isinstance(answers, dict) or len(answers) > 50:
            raise ValidationError('Use a response under 20,000 characters and at most 50 answers.')
        valid_ids = {str(row['id']) for row in assignment.question_snapshot}
        if set(answers) - valid_ids or any(not isinstance(value, str) or len(value) > 2000 for value in answers.values()):
            raise ValidationError('Answer only questions in this assignment.')
        submission, _ = AssignmentSubmission.objects.select_for_update().get_or_create(
            assignment=assignment, student=request.user)
        if submission.status != 'draft':
            raise ValidationError('This response has already been submitted.')
        submission.text, submission.answers = text, answers
        submission.save(update_fields=['text', 'answers'])
        return Response({'saved': True})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def submit(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role != 'student':
            raise PermissionDenied('Only the assigned student can submit.')
        submission, _ = AssignmentSubmission.objects.select_for_update().get_or_create(
            assignment=assignment, student=request.user)
        if submission.status == 'submitted':
            return Response({'status': 'submitted', 'score': str(submission.score) if submission.released_at else None})
        if assignment.status != 'published' or timezone.now() >= assignment.due_at:
            raise ValidationError('This assignment is closed for submissions.')
        if not submission.text.strip() and not submission.answers:
            raise ValidationError('Save an answer before submitting.')
        submission.status, submission.submitted_at = 'submitted', timezone.now()
        if assignment.question_snapshot and not submission.text.strip() and all(q['question_type'] != 'theory' for q in assignment.question_snapshot):
            maximum = sum((Decimal(str(q.get('marks', 1))) for q in assignment.question_snapshot), Decimal('0'))
            earned = sum((Decimal(str(q.get('marks', 1))) for q in assignment.question_snapshot
                          if submission.answers.get(str(q['id']), '').strip().casefold() == str(q['correct_answer']).strip().casefold()), Decimal('0'))
            submission.score = (earned / maximum * assignment.maximum).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        submission.save(update_fields=['status', 'submitted_at', 'score'])
        return Response({'status': 'submitted', 'score': None})

    @action(detail=True, methods=['get'])
    def submissions(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role == 'student':
            raise PermissionDenied('Students cannot list class submissions.')
        return Response([{'id': row.pk, 'student': row.student_id, 'status': row.status,
                          'text': row.text, 'answers': row.answers, 'score': row.score,
                          'feedback': row.feedback, 'released_at': row.released_at}
                         for row in assignment.submissions.select_related('student').all()])

    @action(detail=True, methods=['get'], url_path='my-submission')
    def my_submission(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role != 'student':
            raise PermissionDenied('Only students use this view.')
        row = assignment.submissions.filter(student=request.user).first()
        if not row:
            return Response({'status': 'not_started'})
        return Response({'status': row.status, 'text': row.text, 'answers': row.answers,
                         'score': str(row.score) if row.released_at and row.score is not None else None,
                         'feedback': row.feedback if row.released_at else '', 'submitted_at': row.submitted_at})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def mark(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role == 'student':
            raise PermissionDenied('Only assigned staff can mark submissions.')
        if request.user.role == 'teacher':
            require_assignment(request, assignment.class_arm_id, assignment.term_id, assignment.subject_id)
        row = get_object_or_404(AssignmentSubmission.objects.select_for_update(), pk=request.data.get('submission_id'), assignment=assignment)
        if row.status != 'submitted':
            raise ValidationError('Only submitted work may be marked.')
        try:
            score = Decimal(str(request.data.get('score', row.score)))
        except Exception:
            raise ValidationError('Enter a numeric score.')
        if not score.is_finite() or score < 0 or score > assignment.maximum:
            raise ValidationError('Score must be within this assignment maximum.')
        feedback = request.data.get('feedback', '')
        if not isinstance(feedback, str) or len(feedback) > 5000:
            raise ValidationError('Feedback must be under 5,000 characters.')
        if row.released_at:
            if row.score == score and row.feedback == feedback:
                return Response({'released': True, 'score': str(row.score)})
            raise ValidationError('Released marks are locked.')
        row.score, row.feedback, row.released_at = score, feedback, timezone.now()
        row.save(update_fields=['score', 'feedback', 'released_at'])
        if assignment.kind == 'graded':
            integrate_component(school=self.school, student=row.student, subject=assignment.subject,
                term=assignment.term, class_arm=assignment.class_arm, key=assignment.component_key,
                source=f'assignment:{assignment.pk}', raw_score=score,
                raw_maximum=assignment.maximum, teacher=request.user if request.user.role == 'teacher' else None)
        return Response({'released': True, 'score': str(score)})
