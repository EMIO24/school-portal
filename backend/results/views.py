from rest_framework.throttling import AnonRateThrottle

class ResultCheckThrottle(AnonRateThrottle):
    rate = "10/min"

from accounts.school_access import SchoolModulePermission, require_assignment
"""
backend/results/views.py

Result slip + broadsheet PDF generation via WeasyPrint.
Scratch card generation and public PIN result checking.

Endpoint map:
  GET  /api/results/slip/{student_id}/?term=         â†’ PDF
  GET  /api/results/broadsheet/{class_arm_id}/?term= â†’ PDF
  POST /api/results/positions/compute/?class_arm=&term=
  PATCH /api/results/remarks/{student_id}/?term=
  GET  /api/results/slip-data/{student_id}/?term=    â†’ JSON preview
  POST /api/results/check/                           â†’ PUBLIC PIN check
  POST /api/scratch-cards/generate/                  â†’ Admin, returns CSV
  GET  /api/scratch-cards/                           â†’ Admin list
  GET  /api/scratch-cards/batch-stats/               â†’ Admin batch summary
"""

import csv
import io
import secrets
import string
import zipfile
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.utils.text import slugify
from accounts.permissions import IsSchoolAdmin
from .scratch_pdf import scratch_cards_pdf

from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Count, Q, Sum, Avg, F
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from tenants.mixins import TenantMixin
from tenants.document_branding import school_branding_context, secure_document_response
from academics.models import Term
from enrollment.models import ClassArm, StudentProfile

from .models import ResultRemark, ScratchCard, ReportConfiguration, _generate_serial
from .presentation import presentation, current_configuration, has_complete_published_result, FIELDS
from .serializers import (
    ResultRemarkSerializer, RemarkPatchSerializer,
    ScratchCardSerializer,
)

from gradebook.models import ScoreEntry, AffectiveDomain, PsychomotorDomain
from gradebook.scoring import entry_components
from attendance.models import AttendanceRecord


class ReportConfigurationView(TenantMixin, APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        return Response(current_configuration(self.school))

    @transaction.atomic
    def patch(self, request):
        from tenants.models import PlatformEvent, School
        School.objects.select_for_update().get(pk=self.school.pk)
        values = request.data
        if not isinstance(values, dict) or not values or set(values) - set(FIELDS):
            return Response({'detail': 'Choose supported report options.'}, status=400)
        for name, value in values.items():
            if name == 'layout' and value not in ('classic', 'modern', 'compact'):
                return Response({'detail': 'Choose a supported report layout.'}, status=400)
            if name == 'watermark' and value not in ('none', 'official', 'school'):
                return Response({'detail': 'Choose a supported watermark.'}, status=400)
            if name == 'title' and (not isinstance(value, str) or not value.strip() or len(value.strip()) > 80):
                return Response({'detail': 'Enter a report title of up to 80 characters.'}, status=400)
            if name.startswith('show_') and not isinstance(value, bool):
                return Response({'detail': 'Section visibility must be true or false.'}, status=400)
        config, _ = ReportConfiguration.objects.get_or_create(school=self.school)
        for name, value in values.items():
            setattr(config, name, value.strip() if name == 'title' else value)
        config.save()
        PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email,
            action='school.report_configuration_changed', target=str(self.school.pk),
            details={'school_id': self.school.pk, 'fields': list(values)})
        return Response(current_configuration(self.school))


def _safe_asset_url(value):
    """Allow only absolute HTTP(S) asset URLs in PDF templates."""
    if isinstance(value, str) and value.startswith(('http://', 'https://')):
        return value
    return ''


def _simple_pdf_bytes(lines):
    """
    Minimal PDF fallback for environments where WeasyPrint native
    dependencies are unavailable.
    """
    sanitized = []
    for line in lines:
        text = str(line).encode('ascii', 'replace').decode('ascii')
        text = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        sanitized.append(text)

    content_lines = ['BT', '/F1 12 Tf', '50 780 Td']
    for index, line in enumerate(sanitized):
        if index == 0:
            content_lines.append(f'({line}) Tj')
        else:
            content_lines.append(f'0 -18 Td ({line}) Tj')
    content_lines.append('ET')
    stream = '\n'.join(content_lines).encode('ascii')

    objects = [
        b'1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj',
        b'2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj',
        b'3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj',
        b'4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj',
        b'5 0 obj << /Length ' + str(len(stream)).encode('ascii') + b' >> stream\n' + stream + b'\nendstream endobj',
    ]

    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj + b'\n')
    xref_pos = len(pdf)
    pdf.extend(f'xref\n0 {len(offsets)}\n'.encode('ascii'))
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    pdf.extend(
        f'trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF'.encode('ascii')
    )
    return bytes(pdf)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Data assembly helper
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _assemble_slip_data(school, student, term, *, preview=False):
    """
    Build the complete context dict for both the HTML template and JSON preview.
    This is the single source of truth for all result slip data.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Score entries for this student/term (published only for students, all for admin)
    scores = (
        ScoreEntry.objects
        .filter(school=school, student=student, term=term, **({} if preview else {'is_published': True}))
        .select_related('subject', 'policy', 'class_arm__class_level')
        .order_by('subject__name')
    )

    score_rows = []
    for entry in scores:
        score_rows.append({
            'subject':     entry.subject.name,
            'components': entry_components(entry),
            'grading_bands': entry.policy.bands if entry.policy_id else [],
            'first_test':  float(entry.first_test  or 0),
            'second_test': float(entry.second_test or 0),
            'assignment':  float(entry.assignment  or 0),
            'project':     float(entry.project     or 0),
            'ca_total':    float(entry.ca_total    or 0),
            'exam_score':  float(entry.exam_score  or 0),
            'total_score': float(entry.total_score or 0),
            'grade':       entry.grade,
            'remark':      entry.remark,
        })

    # Affective domain
    affective = AffectiveDomain.objects.filter(
        school=school, student=student, term=term
    ).first()

    affective_rows = []
    if affective:
        trait_map = [
            ('Punctuality',              affective.punctuality),
            ('Neatness',                 affective.neatness),
            ('Honesty',                  affective.honesty),
            ('Attentiveness',            affective.attentiveness),
            ('Relationship with Others', affective.relationship_with_others),
            ('Leadership',               affective.leadership),
            ('Creativity',               affective.creativity),
            ('Sport & Games',            affective.sport_games),
            ('Handling of Tools',        affective.handling_of_tools),
        ]
        rating_desc = {1: 'Poor', 2: 'Below Average', 3: 'Average', 4: 'Good', 5: 'Excellent'}
        affective_rows = [
            {'trait': t, 'rating': r, 'descriptor': rating_desc[r]}
            for t, r in trait_map
        ]

    # Psychomotor domain
    psychomotor = PsychomotorDomain.objects.filter(
        school=school, student=student, term=term
    ).first()

    psychomotor_rows = []
    if psychomotor:
        skills = [
            ('Handwriting',    psychomotor.handwriting),
            ('Drawing',        psychomotor.drawing),
            ('Verbal Fluency', psychomotor.verbal_fluency),
            ('Musical Skills', psychomotor.musical_skills),
        ]
        rating_desc = {1: 'Poor', 2: 'Below Average', 3: 'Average', 4: 'Good', 5: 'Excellent'}
        psychomotor_rows = [
            {'skill': s, 'rating': r, 'descriptor': rating_desc[r]}
            for s, r in skills
        ]

    # Remarks + position
    remark_obj = ResultRemark.objects.filter(
        school=school, student=student, term=term
    ).first()

    # Student profile fields
    profile = getattr(student, 'student_profile', None)
    report_class = scores[0].class_arm if scores else getattr(profile, 'current_class', None)

    # Only explicitly recorded, finalized attendance in the report's class
    # is authoritative. A missing register is unknown, not an absence.
    att_summary = AttendanceRecord.objects.filter(
        student=student, attendance_session__school=school,
        attendance_session__term=term, attendance_session__class_arm=report_class,
        attendance_session__is_finalized=True,
    ).aggregate(
        total=Count('id'),
        present=Count('id', filter=Q(status='present')),
        late=Count('id', filter=Q(status='late')),
        excused=Count('id', filter=Q(status='excused')),
    )
    recorded_sessions = att_summary['total'] or 0
    effective_sessions = max(recorded_sessions - (att_summary['excused'] or 0), 0)
    present_sessions = (att_summary['present'] or 0) + (att_summary['late'] or 0)

    # Class size for "out of N students"
    class_size = ResultRemark.objects.filter(
        school=school, term=term,
        class_arm=report_class
    ).count()

    return {
        # School
        **presentation(school, term, preview=preview),
        'unpublished_preview': preview,

        # Term / session
        'term_name':      term.name,
        'session_name':   getattr(term, 'session', {}) and str(term.session) or '',
        'next_term_date': getattr(term, 'next_term_begins', ''),

        # Student
        'student_name':   f"{student.last_name} {student.first_name}".strip(),
        'admission_no':   getattr(profile, 'admission_number', ''),
        'class_name':     str(report_class or ''),
        'gender':         getattr(profile, 'gender', ''),
        'date_of_birth':  getattr(profile, 'date_of_birth', ''),
        'photo_url':      _safe_asset_url(getattr(profile, 'photo_url', '')),

        # Scores
        'score_rows':     score_rows,
        'num_subjects':   len(score_rows),
        'total_score':    sum(r['total_score'] for r in score_rows),
        'average_score':  (
            round(sum(r['total_score'] for r in score_rows) / len(score_rows), 1)
            if score_rows else 0
        ),

        # Position
        'position':       getattr(remark_obj, 'computed_position', None),
        'class_size':     class_size or '—',

        # Domains
        'affective_rows':   affective_rows,
        'psychomotor_rows': psychomotor_rows,

        # Attendance
        'days_present':   present_sessions,
        'total_days':     recorded_sessions,
        'att_percentage': round(present_sessions / effective_sessions * 100, 1) if effective_sessions else 0,

        # Remarks
        'class_teacher_remark': getattr(remark_obj, 'class_teacher_remark', ''),
        'principal_remark':     getattr(remark_obj, 'principal_remark', ''),
    }


def _render_pdf(template_name, context, orientation='portrait'):
    """Render a WeasyPrint PDF and return raw bytes."""
    try:
        from weasyprint import HTML, CSS
        html_string = render_to_string(template_name, context)
        base_css = CSS(string=f'@page {{ size: A4 {orientation}; margin: 12mm; }}')
        return HTML(string=html_string).write_pdf(stylesheets=[base_css])
    except Exception:
        if template_name == 'result_slip.html':
            from .report_pdf import text_report_pdf
            lines = [f"Student: {context.get('student_name', '')}",
                     f"Admission: {context.get('admission_no', '')}",
                     f"Class: {context.get('class_name', '')}",
                     f"Term: {context.get('term_name', '')} | Session: {context.get('session_name', '')}"]
            for row in context.get('score_rows', []):
                parts = ', '.join(f"{part['name']} {part['score']}/{part['maximum']}"
                                  for part in row.get('components', []))
                lines.append(f"{row['subject']}: {parts}; Total {row['total_score']}; Grade {row['grade']}; {row['remark']}")
            lines.extend([f"Total: {context.get('total_score', '')}",
                          f"Average: {context.get('average_score', '')}"])
            if context.get('show_position'):
                lines.append(f"Position: {context.get('position') or 'Not calculated'}")
            if context.get('show_attendance'):
                lines.append(f"Attendance: {context.get('days_present', 0)}/{context.get('total_days', 0)} finalized sessions"
                             if context.get('total_days') else 'Attendance: Not finalized')
            if context.get('show_comments'):
                lines.extend([f"Teacher: {context.get('class_teacher_remark', '')}",
                              f"Principal: {context.get('principal_remark', '')}"])
            if context.get('unpublished_preview'):
                lines.insert(0, 'UNPUBLISHED PREVIEW - NOT AN OFFICIAL RESULT')
            return text_report_pdf(context.get('title', 'Student Academic Report'), lines, context)
        title = context.get('school_name', 'School Portal')
        subtitle = context.get('student_name') or context.get('class_name') or 'Report'
        term = context.get('term_name', '')
        session = context.get('session_name', '')
        return _simple_pdf_bytes([
            title,
            subtitle,
            f'Term: {term}',
            f'Session: {session}',
            'PDF preview fallback generated by the server.',
        ])


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Position computation
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ComputePositionsView(TenantMixin, APIView):
    permission_classes = [SchoolModulePermission]

    def post(self, request):
        """
        Compute and persist class positions for all students in a class arm + term.
        Ranking is by sum of published total_score across all subjects (descending).
        Tied students receive the same position; the next rank is skipped (standard competition ranking).
        """
        class_arm_id = request.query_params.get('class_arm')
        term_id      = request.query_params.get('term')

        if not (class_arm_id and term_id):
            return Response(
                {'detail': 'class_arm and term params required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not (str(class_arm_id).isdigit() and str(term_id).isdigit() and
                ClassArm.objects.filter(pk=class_arm_id, school=self.school).exists() and
                Term.objects.filter(pk=term_id, session__school=self.school).exists()):
            return Response({'detail': 'Choose a class and term in this school.'}, status=400)
        class_scores = ScoreEntry.objects.filter(school=self.school, class_arm_id=class_arm_id, term_id=term_id)
        counts = list(class_scores.values('student_id').annotate(
            total=Count('id'), published=Count('id', filter=Q(is_published=True))))
        if not counts or any(row['published'] != row['total'] for row in counts) or len({row['total'] for row in counts}) != 1:
            return Response({'detail': 'Publish complete results for every student before computing positions.'}, status=409)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get all students in this class arm, with score aggregates in one query
        score_filter = Q(
            score_entries__school=self.school,
            score_entries__term_id=term_id,
            score_entries__class_arm_id=class_arm_id,
            score_entries__is_published=True,
        )
        students = User.objects.filter(
            school=self.school,
            role='student',
            pk__in=[row['student_id'] for row in counts],
        ).annotate(
            agg_total=Sum('score_entries__total_score', filter=score_filter),
            agg_avg=Avg('score_entries__total_score',   filter=score_filter),
            agg_count=Count('score_entries',             filter=score_filter),
        )

        student_totals = [
            {
                'student': s,
                'total':   s.agg_total  or Decimal('0'),
                'average': s.agg_avg    or Decimal('0'),
                'count':   s.agg_count  or 0,
            }
            for s in students
        ]

        # Sort descending by total
        student_totals.sort(key=lambda x: x['total'], reverse=True)

        # Assign competition-style positions (ties share rank, next skips)
        position = 1
        for i, row in enumerate(student_totals):
            if i > 0 and row['total'] < student_totals[i - 1]['total']:
                position = i + 1

            ResultRemark.objects.update_or_create(
                school=self.school,
                student=row['student'],
                term_id=term_id,
                defaults={
                    'class_arm_id':    class_arm_id,
                    'computed_position': position,
                    'total_score':     row['total'],
                    'average_score':   round(row['average'], 2),
                    'subjects_offered': row['count'],
                },
            )

        return Response({
            'computed': len(student_totals),
            'class_arm': class_arm_id,
            'term': term_id,
        })


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Remarks PATCH
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ResultRemarkView(TenantMixin, APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request, student_id):
        term_id = request.query_params.get('term')
        obj = ResultRemark.objects.filter(
            school=self.school, student_id=student_id, term_id=term_id
        ).first()
        if not obj:
            return Response({'detail': 'No result found.'}, status=404)
        return Response(ResultRemarkSerializer(obj).data)

    @transaction.atomic
    def patch(self, request, student_id):
        from gradebook.lifecycle import lock_school, require_unpublished
        lock_school(self.school)
        term_id = request.query_params.get('term')
        if not term_id:
            return Response({'detail': 'term param required.'}, status=400)

        try:
            profile = StudentProfile.objects.select_related('user', 'current_class').get(
                user_id=student_id,
                user__role='student',
                school=self.school,
            )
            term = Term.objects.get(pk=term_id, session__school=self.school)
        except (StudentProfile.DoesNotExist, Term.DoesNotExist):
            return Response({'detail': 'Student or term not found.'}, status=404)

        require_unpublished(self.school, profile.user, term)
        class_arm_id = request.data.get('class_arm') or getattr(profile, 'current_class_id', None)
        if not class_arm_id:
            return Response({'detail': 'class_arm is required for this student.'}, status=400)
        try:
            class_arm = ClassArm.objects.get(pk=class_arm_id, school=self.school)
        except ClassArm.DoesNotExist:
            return Response({'detail': 'Class not found.'}, status=404)
        if profile.current_class_id and class_arm.pk != profile.current_class_id:
            return Response({'detail': 'Class does not match this student.'}, status=400)

        obj, _ = ResultRemark.objects.get_or_create(
            school=self.school,
            student=profile.user,
            term=term,
            defaults={'class_arm': class_arm},
        )
        if obj.class_arm_id != class_arm.pk:
            return Response({'detail': 'Class does not match this result remark.'}, status=400)
        ser = RemarkPatchSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ResultRemarkSerializer(obj).data)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Class results list (for admin management table)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ClassResultsView(TenantMixin, APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request):
        class_arm_id = request.query_params.get('class_arm')
        term_id      = request.query_params.get('term')

        if not (class_arm_id and term_id):
            return Response({'detail': 'class_arm and term required.'}, status=400)

        remarks = (
            ResultRemark.objects
            .filter(school=self.school, class_arm_id=class_arm_id, term_id=term_id)
            .select_related('student')
            .order_by('computed_position', 'student__last_name')
        )
        return Response(ResultRemarkSerializer(remarks, many=True).data)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Slip data JSON (browser preview)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class SlipDataView(TenantMixin, APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request, student_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        term_id = request.query_params.get('term')
        if not term_id:
            return Response({'detail': 'term param required.'}, status=400)

        try:
            from academics.models import Term
            student = User.objects.get(pk=student_id, school=self.school, role='student')
            term    = Term.objects.get(pk=term_id, session__school=self.school)
        except Exception:
            return Response({'detail': 'Student or term not found.'}, status=404)

        preview = request.query_params.get('preview') == '1' and request.user.role == 'school_admin'
        if not preview and not has_complete_published_result(self.school, student, term):
            return Response({'detail': 'Result not available.'}, status=404)
        data = _assemble_slip_data(self.school, student, term, preview=preview)
        return Response(data)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PDF: Result Slip
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ResultSlipPDFView(TenantMixin, APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request, student_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        term_id = request.query_params.get('term')

        try:
            student = User.objects.get(pk=student_id, school=self.school, role='student')
            from academics.models import Term
            term = Term.objects.get(pk=term_id, session__school=self.school)
        except Exception:
            return Response({'detail': 'Student or term not found.'}, status=404)

        preview = request.query_params.get('preview') == '1' and request.user.role == 'school_admin'
        if not preview and not has_complete_published_result(self.school, student, term):
            return Response({'detail': 'Result not available.'}, status=404)
        context = _assemble_slip_data(self.school, student, term, preview=preview)
        pdf     = _render_pdf('result_slip.html', context, orientation='portrait')

        filename = f"result_{student_id}_term{term_id}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return secure_document_response(response)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PDF: Broadsheet
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class BroadsheetPDFView(TenantMixin, APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request, class_arm_id):
        from django.contrib.auth import get_user_model
        User    = get_user_model()
        term_id = request.query_params.get('term')

        if not term_id:
            return Response({'detail': 'term param required.'}, status=400)

        if not str(term_id).isdigit():
            return Response({'detail': 'Choose a valid term.'}, status=400)

        counts = list(ScoreEntry.objects.filter(
            school=self.school, class_arm_id=class_arm_id, term_id=term_id,
        ).values('student_id').annotate(
            total=Count('id'), published=Count('id', filter=Q(is_published=True)),
            score_total=Sum('total_score'),
        ))
        if not counts:
            return Response({'detail': 'No result is available for this class and term.'}, status=404)
        if any(row['published'] != row['total'] for row in counts) or len({row['total'] for row in counts}) != 1:
            return Response({'detail': 'Publish complete class results before exporting the broadsheet.'}, status=409)

        # All subjects with at least one published entry in this class/term
        subjects = list(
            ScoreEntry.objects
            .filter(
                school=self.school,
                class_arm_id=class_arm_id,
                term_id=term_id,
                is_published=True,
            )
            .values_list('subject__name', flat=True)
            .distinct()
            .order_by('subject__name')
        )

        # All students with a remark (i.e. positions computed)
        remarks = list((
            ResultRemark.objects
            .filter(school=self.school, class_arm_id=class_arm_id, term_id=term_id)
            .select_related('student', 'student__student_profile')
            .order_by('computed_position', 'student__last_name')
        ))
        totals = {row['student_id']: row for row in counts}
        if (len(remarks) != len(totals) or any(
                remark.student_id not in totals or
                remark.total_score != totals[remark.student_id]['score_total'] or
                remark.subjects_offered != totals[remark.student_id]['total']
                for remark in remarks)):
            return Response({'detail': 'Recompute class positions before exporting the broadsheet.'}, status=409)

        entries_by_student = {}
        for entry in ScoreEntry.objects.filter(school=self.school, class_arm_id=class_arm_id,
                term_id=term_id, is_published=True).select_related('subject'):
            entries_by_student.setdefault(entry.student_id, {})[entry.subject.name] = entry

        # Build row data for each student
        rows = []
        for i, remark in enumerate(remarks):
            student = remark.student
            profile = getattr(student, 'student_profile', None)

            # Scores keyed by subject name
            entries = entries_by_student.get(student.pk, {})

            subject_scores = []
            for subj in subjects:
                e = entries.get(subj)
                subject_scores.append({
                    'total': float(e.total_score) if e else '',
                    'grade': e.grade if e else '',
                })

            rows.append({
                'sn':           i + 1,
                'name':         f"{student.last_name} {student.first_name}".strip(),
                'admission_no': getattr(profile, 'admission_number', ''),
                'scores':       subject_scores,
                'total':        float(remark.total_score or 0),
                'average':      float(remark.average_score or 0),
                'position':     remark.computed_position,
                'rank_class':   (
                    'rank-gold'   if remark.computed_position == 1 else
                    'rank-silver' if remark.computed_position == 2 else
                    'rank-bronze' if remark.computed_position == 3 else ''
                ),
            })

        from academics.models import Term
        try:
            term_obj = Term.objects.get(pk=term_id, session__school=self.school)
        except Term.DoesNotExist:
            return Response({'detail': 'Term not found.'}, status=404)

        from enrollment.models import ClassArm
        try:
            class_arm = ClassArm.objects.get(pk=class_arm_id, school=self.school)
        except ClassArm.DoesNotExist:
            return Response({'detail': 'Class not found.'}, status=404)

        context = {
            **school_branding_context(self.school),
            'class_name':     str(class_arm),
            'term_name':      term_obj.name,
            'session_name':   str(getattr(term_obj, 'session', '')),
            'subjects':       subjects,
            'rows':           rows,
            'total_students': len(rows),
            'generated_at':   timezone.now(),
        }

        pdf = _render_pdf('broadsheet.html', context, orientation='landscape')
        filename = f"broadsheet_class{class_arm_id}_term{term_id}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return secure_document_response(response)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ZIP: All slips for a class
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class AllSlipsZipView(TenantMixin, APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request, class_arm_id):
        from django.contrib.auth import get_user_model
        from academics.models import Term
        User    = get_user_model()
        term_id = request.query_params.get('term')

        if not term_id:
            return Response({'detail': 'term param required.'}, status=400)

        try:
            term = Term.objects.get(pk=term_id, session__school=self.school)
        except Term.DoesNotExist:
            return Response({'detail': 'Term not found.'}, status=404)

        if not ClassArm.objects.filter(pk=class_arm_id, school=self.school).exists():
            return Response({'detail': 'Class not found.'}, status=404)
        published_students = ScoreEntry.objects.filter(
            school=self.school, class_arm_id=class_arm_id, term=term,
        ).values('student_id').annotate(
            total=Count('id'), published=Count('id', filter=Q(is_published=True)),
        ).filter(total=F('published')).values_list('student_id', flat=True)
        students = User.objects.filter(
            school=self.school, role='student', pk__in=published_students,
        ).order_by('last_name', 'first_name')
        if not students.exists():
            return Response({'detail': 'No published results are available for this class and term.'}, status=404)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for student in students:
                ctx = _assemble_slip_data(self.school, student, term)
                pdf = _render_pdf('result_slip.html', ctx, orientation='portrait')
                safe_name = f"{student.last_name}_{student.first_name}".replace(' ', '_')
                zf.writestr(f"{safe_name}_result.pdf", pdf)

        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = (
            f'attachment; filename="results_class{class_arm_id}_term{term_id}.zip"'
        )
        return secure_document_response(response)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Scratch Card: Generate (Admin)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ScratchCardGenerateView(TenantMixin, APIView):
    permission_classes = [IsSchoolAdmin]

    @transaction.atomic
    def post(self, request):
        try:
            quantity = int(request.data.get('quantity', 0))
            amount = Decimal(str(request.data.get('price', '0')))
            if not amount.is_finite() or amount < 0 or amount >= 1000000 or amount.as_tuple().exponent < -2:
                raise ValueError()
        except (ValueError, TypeError, InvalidOperation):
            return Response({'detail': 'Enter a valid quantity and non-negative price with up to two decimal places.'}, status=400)
        batch_name = request.data.get('batch_name', '').strip()
        term_id    = request.data.get('term_id')
        price      = request.data.get('price', '0')

        if quantity < 1 or quantity > 500:
            return Response({'detail': 'quantity must be between 1 and 500.'}, status=400)
        if not batch_name:
            return Response({'detail': 'batch_name is required.'}, status=400)

        if term_id:
            from academics.models import Term
            if not str(term_id).isdigit() or not Term.objects.filter(pk=term_id, session__school=self.school).exists():
                return Response({'detail': 'Choose a term belonging to this school.'}, status=400)
        if len(batch_name) > 100:
            return Response({'detail': 'Batch name must be at most 100 characters.'}, status=400)
        cards_to_create = []
        csv_rows = [['serial_number', 'pin']]

        for _ in range(quantity):
            # Generate unique serial
            while True:
                serial = _generate_serial(self.school.slug)
                if not ScratchCard.objects.filter(serial_number=serial).exists():
                    break

            plain_pin = ''.join(secrets.choice(string.digits) for _ in range(10))
            hashed    = make_password(plain_pin)

            cards_to_create.append(ScratchCard(
                school       = self.school,
                serial_number= serial,
                pin_hash     = hashed,
                batch_name   = batch_name,
                term_id      = term_id or None,
                price        = price,
                generated_by = request.user,
            ))
            csv_rows.append([serial, plain_pin])

        # Render before saving; failed exports must not leave an inaccessible PIN batch.
        pdf = scratch_cards_pdf(school_branding_context(self.school), batch_name, csv_rows[1:])
        ScratchCard.objects.bulk_create(cards_to_create)
        filename = f"scratch_cards_{slugify(batch_name) or 'batch'}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Cache-Control'] = 'no-store'
        return secure_document_response(response)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Scratch Card: List + Batch Stats (Admin)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class ScratchCardListView(TenantMixin, APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        batch = request.query_params.get('batch')
        qs = ScratchCard.objects.filter(school=self.school)
        if batch:
            qs = qs.filter(batch_name=batch)
        serializer = ScratchCardSerializer(qs, many=True)
        return Response(serializer.data)


class ScratchCardRevokeView(TenantMixin, APIView):
    permission_classes = [IsSchoolAdmin]

    @transaction.atomic
    def post(self, request, card_id):
        from tenants.models import PlatformEvent
        card = ScratchCard.objects.select_for_update().filter(school=self.school, pk=card_id).first()
        if not card:
            return Response({'detail': 'Card not found.'}, status=404)
        if card.is_used:
            return Response({'detail': 'A used card cannot be revoked.'}, status=409)
        if card.revoked_at:
            return Response({'revoked': True})
        card.revoked_at = timezone.now()
        card.revoked_by = request.user
        card.save(update_fields=['revoked_at', 'revoked_by'])
        PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email,
            action='school.scratch_card_revoked', target=str(card.pk),
            details={'school_id': self.school.pk, 'card_id': card.pk})
        return Response({'revoked': True})


class ScratchCardBatchStatsView(TenantMixin, APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        from django.db.models import Min
        batches = (
            ScratchCard.objects
            .filter(school=self.school)
            .values('batch_name')
            .annotate(
                total     = Count('id'),
                used      = Count('id', filter=Q(is_used=True)),
                unused    = Count('id', filter=Q(is_used=False, revoked_at__isnull=True)),
                revoked   = Count('id', filter=Q(revoked_at__isnull=False)),
                created_at= Min('created_at'),
            )
            .order_by('-created_at')
        )
        return Response(list(batches))


class ScratchCardUnusedPDFView(TenantMixin, APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        batch = request.query_params.get('batch', '').strip()
        if not batch:
            return Response({'detail': 'batch param required.'}, status=400)
        cards = ScratchCard.objects.filter(school=self.school, batch_name=batch, is_used=False, revoked_at__isnull=True)
        pdf = scratch_cards_pdf(school_branding_context(self.school), batch, ((card.serial_number, '') for card in cards), include_pins=False)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="unused_{slugify(batch) or "batch"}.pdf"'
        response['Cache-Control'] = 'no-store'
        return secure_document_response(response)


class ScratchCardUnusedCSVView(ScratchCardUnusedPDFView):
    # Retain the legacy URL, but all report downloads now return PDF.
    pass


class PublicResultCheckView(APIView):
    throttle_classes = [ResultCheckThrottle]
    """
    Public endpoint â€” no login required.
    Accepts admission_number + serial_number + pin.
    Verifies the scratch card, marks it used, returns full result JSON.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        generic_error = Response(
            {'detail': 'The supplied result-checking details are invalid or unavailable.'},
            status=403,
            headers={'Cache-Control': 'no-store'},
        )
        admission_number = str(request.data.get('admission_number') or '').strip().upper()
        serial_number    = str(request.data.get('serial_number') or '').strip().upper()
        pin              = str(request.data.get('pin') or '').strip()

        if not (admission_number and serial_number and pin) or max(map(len, (admission_number, serial_number, pin))) > 100:
            return generic_error

        # Look up card
        try:
            card = ScratchCard.objects.select_related('school').get(
                serial_number=serial_number
            )
        except ScratchCard.DoesNotExist:
            return generic_error

        if not card.school.is_active or card.school.approval_status != 'approved':
            return generic_error

        # Verify PIN
        if not check_password(pin, card.pin_hash):
            return generic_error

        # Already used?
        if card.is_used or card.revoked_at:
            return generic_error

        # Find student by admission number within that school
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            from enrollment.models import StudentProfile
            profile = StudentProfile.objects.select_related('user').get(
                school=card.school,
                admission_number=admission_number,
            )
            student = profile.user
        except StudentProfile.DoesNotExist:
            return generic_error

        # Determine term â€” use card's term if set, else current term for the school
        if card.term:
            term = card.term
        else:
            from academics.models import Term
            term = Term.objects.filter(
                session__school=card.school, is_current=True
            ).first()
            if not term:
                return generic_error

        # A single-use card must not be consumed for an unavailable result.
        if not has_complete_published_result(card.school, student, term):
            return generic_error

        # Mark card used atomically to prevent double-use race condition
        updated = ScratchCard.objects.filter(pk=card.pk, is_used=False, revoked_at__isnull=True).update(
            is_used=True,
            used_at=timezone.now(),
            used_by_student=student,
        )
        if not updated:
            return generic_error

        # Assemble and return result data
        data = _assemble_slip_data(card.school, student, term)
        return Response(data, headers={'Cache-Control': 'no-store'})

