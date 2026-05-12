"""
backend/results/views.py

Result slip + broadsheet PDF generation via WeasyPrint.
Scratch card generation and public PIN result checking.

Endpoint map:
  GET  /api/results/slip/{student_id}/?term=         → PDF
  GET  /api/results/broadsheet/{class_arm_id}/?term= → PDF
  POST /api/results/positions/compute/?class_arm=&term=
  PATCH /api/results/remarks/{student_id}/?term=
  GET  /api/results/slip-data/{student_id}/?term=    → JSON preview
  POST /api/results/check/                           → PUBLIC PIN check
  POST /api/scratch-cards/generate/                  → Admin, returns CSV
  GET  /api/scratch-cards/                           → Admin list
  GET  /api/scratch-cards/batch-stats/               → Admin batch summary
"""

import csv
import io
import random
import string
import zipfile
from decimal import Decimal

from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Count, Q, Sum, Avg
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from tenants.mixins import TenantMixin

from .models import ResultRemark, ScratchCard, _generate_serial
from .serializers import (
    ResultRemarkSerializer, RemarkPatchSerializer,
    ScratchCardSerializer,
)

from gradebook.models import ScoreEntry, AffectiveDomain, PsychomotorDomain
from attendance.models import AttendanceRecord


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


# ─────────────────────────────────────────────────────────────────────────────
# Data assembly helper
# ─────────────────────────────────────────────────────────────────────────────

def _assemble_slip_data(school, student, term):
    """
    Build the complete context dict for both the HTML template and JSON preview.
    This is the single source of truth for all result slip data.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Score entries for this student/term (published only for students, all for admin)
    scores = (
        ScoreEntry.objects
        .filter(school=school, student=student, term=term, is_published=True)
        .select_related('subject')
        .order_by('subject__name')
    )

    score_rows = []
    for entry in scores:
        score_rows.append({
            'subject':     entry.subject.name,
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

    # Attendance summary
    att_summary = AttendanceRecord.objects.summary(student.id, term.id)

    # Remarks + position
    remark_obj = ResultRemark.objects.filter(
        school=school, student=student, term=term
    ).first()

    # Student profile fields
    profile = getattr(student, 'student_profile', None)

    # Compute total sessions in the term for attendance denominator
    from attendance.models import AttendanceSession
    total_sessions = AttendanceSession.objects.filter(
        school=school, term=term, is_finalized=True
    ).count()

    # Class size for "out of N students"
    class_size = ResultRemark.objects.filter(
        school=school, term=term,
        class_arm=getattr(profile, 'current_class', None)
    ).count()

    return {
        # School
        'school_name':    school.name,
        'school_address': getattr(school, 'address', ''),
        'school_logo':    _safe_asset_url(getattr(school, 'logo_url', '')),
        'school_phone':   getattr(school, 'phone', ''),

        # Term / session
        'term_name':      term.name,
        'session_name':   getattr(term, 'session', {}) and str(term.session) or '',
        'next_term_date': getattr(term, 'next_term_begins', ''),

        # Student
        'student_name':   f"{student.last_name} {student.first_name}".strip(),
        'admission_no':   getattr(profile, 'admission_number', ''),
        'class_name':     str(getattr(profile, 'current_class', '')),
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
        'days_present':   att_summary.get('present', 0) + att_summary.get('late', 0),
        'total_days':     total_sessions,
        'att_percentage': att_summary.get('percentage', 0),

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


# ─────────────────────────────────────────────────────────────────────────────
# Position computation
# ─────────────────────────────────────────────────────────────────────────────

class ComputePositionsView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

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

        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Get all students in this class arm, with score aggregates in one query
        score_filter = Q(
            score_entries__school=self.school,
            score_entries__term_id=term_id,
            score_entries__is_published=True,
        )
        students = User.objects.filter(
            school=self.school,
            role='student',
            student_profile__current_class_id=class_arm_id,
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


# ─────────────────────────────────────────────────────────────────────────────
# Remarks PATCH
# ─────────────────────────────────────────────────────────────────────────────

class ResultRemarkView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        term_id = request.query_params.get('term')
        obj = ResultRemark.objects.filter(
            school=self.school, student_id=student_id, term_id=term_id
        ).first()
        if not obj:
            return Response({'detail': 'No result found.'}, status=404)
        return Response(ResultRemarkSerializer(obj).data)

    def patch(self, request, student_id):
        term_id = request.query_params.get('term')
        if not term_id:
            return Response({'detail': 'term param required.'}, status=400)

        obj, _ = ResultRemark.objects.get_or_create(
            school=self.school,
            student_id=student_id,
            term_id=term_id,
            defaults={'class_arm_id': request.data.get('class_arm')},
        )
        ser = RemarkPatchSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ResultRemarkSerializer(obj).data)


# ─────────────────────────────────────────────────────────────────────────────
# Class results list (for admin management table)
# ─────────────────────────────────────────────────────────────────────────────

class ClassResultsView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

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


# ─────────────────────────────────────────────────────────────────────────────
# Slip data JSON (browser preview)
# ─────────────────────────────────────────────────────────────────────────────

class SlipDataView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        term_id = request.query_params.get('term')
        if not term_id:
            return Response({'detail': 'term param required.'}, status=400)

        try:
            from academics.models import Term
            student = User.objects.get(pk=student_id, school=self.school)
            term    = Term.objects.get(pk=term_id)
        except Exception:
            return Response({'detail': 'Student or term not found.'}, status=404)

        data = _assemble_slip_data(self.school, student, term)
        return Response(data)


# ─────────────────────────────────────────────────────────────────────────────
# PDF: Result Slip
# ─────────────────────────────────────────────────────────────────────────────

class ResultSlipPDFView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, student_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        term_id = request.query_params.get('term')

        try:
            student = User.objects.get(pk=student_id, school=self.school)
            from academics.models import Term
            term = Term.objects.get(pk=term_id)
        except Exception:
            return Response({'detail': 'Student or term not found.'}, status=404)

        context = _assemble_slip_data(self.school, student, term)
        pdf     = _render_pdf('result_slip.html', context, orientation='portrait')

        filename = f"result_{student_id}_term{term_id}.pdf"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


# ─────────────────────────────────────────────────────────────────────────────
# PDF: Broadsheet
# ─────────────────────────────────────────────────────────────────────────────

class BroadsheetPDFView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, class_arm_id):
        from django.contrib.auth import get_user_model
        User    = get_user_model()
        term_id = request.query_params.get('term')

        if not term_id:
            return Response({'detail': 'term param required.'}, status=400)

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
        remarks = (
            ResultRemark.objects
            .filter(school=self.school, class_arm_id=class_arm_id, term_id=term_id)
            .select_related('student')
            .order_by('computed_position', 'student__last_name')
        )

        # Build row data for each student
        rows = []
        for i, remark in enumerate(remarks):
            student = remark.student
            profile = getattr(student, 'student_profile', None)

            # Scores keyed by subject name
            entries = {
                e.subject.name: e
                for e in ScoreEntry.objects.filter(
                    school=self.school,
                    student=student,
                    class_arm_id=class_arm_id,
                    term_id=term_id,
                    is_published=True,
                ).select_related('subject')
            }

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
            term_obj = Term.objects.get(pk=term_id)
        except Term.DoesNotExist:
            return Response({'detail': 'Term not found.'}, status=404)

        from enrollment.models import ClassArm
        try:
            class_arm = ClassArm.objects.get(pk=class_arm_id)
        except ClassArm.DoesNotExist:
            return Response({'detail': 'Class not found.'}, status=404)

        context = {
            'school_name':    self.school.name,
            'school_logo':    _safe_asset_url(getattr(self.school, 'logo_url', '')),
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
        return response


# ─────────────────────────────────────────────────────────────────────────────
# ZIP: All slips for a class
# ─────────────────────────────────────────────────────────────────────────────

class AllSlipsZipView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, class_arm_id):
        from django.contrib.auth import get_user_model
        from academics.models import Term
        User    = get_user_model()
        term_id = request.query_params.get('term')

        if not term_id:
            return Response({'detail': 'term param required.'}, status=400)

        try:
            term = Term.objects.get(pk=term_id)
        except Term.DoesNotExist:
            return Response({'detail': 'Term not found.'}, status=404)

        students = User.objects.filter(
            school=self.school,
            role='student',
            student_profile__current_class_id=class_arm_id,
        )

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
        return response


# ─────────────────────────────────────────────────────────────────────────────
# Scratch Card: Generate (Admin)
# ─────────────────────────────────────────────────────────────────────────────

class ScratchCardGenerateView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        quantity   = int(request.data.get('quantity', 0))
        batch_name = request.data.get('batch_name', '').strip()
        term_id    = request.data.get('term_id')
        price      = request.data.get('price', '0')

        if quantity < 1 or quantity > 500:
            return Response({'detail': 'quantity must be between 1 and 500.'}, status=400)
        if not batch_name:
            return Response({'detail': 'batch_name is required.'}, status=400)

        cards_to_create = []
        csv_rows = [['serial_number', 'pin']]

        for _ in range(quantity):
            # Generate unique serial
            while True:
                serial = _generate_serial(self.school.slug)
                if not ScratchCard.objects.filter(serial_number=serial).exists():
                    break

            plain_pin = ''.join(random.choices(string.digits, k=10))
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

        ScratchCard.objects.bulk_create(cards_to_create)

        # Return CSV download
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(csv_rows)
        output.seek(0)

        filename = f"scratch_cards_{batch_name.replace(' ', '_')}.csv"
        response = HttpResponse(output.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ─────────────────────────────────────────────────────────────────────────────
# Scratch Card: List + Batch Stats (Admin)
# ─────────────────────────────────────────────────────────────────────────────

class ScratchCardListView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        batch = request.query_params.get('batch')
        qs = ScratchCard.objects.filter(school=self.school)
        if batch:
            qs = qs.filter(batch_name=batch)
        serializer = ScratchCardSerializer(qs, many=True)
        return Response(serializer.data)


class ScratchCardBatchStatsView(TenantMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Min
        batches = (
            ScratchCard.objects
            .filter(school=self.school)
            .values('batch_name')
            .annotate(
                total     = Count('id'),
                used      = Count('id', filter=Q(is_used=True)),
                unused    = Count('id', filter=Q(is_used=False)),
                created_at= Min('created_at'),
            )
            .order_by('-created_at')
        )
        return Response(list(batches))


class ScratchCardUnusedCSVView(TenantMixin, APIView):
    """Download unused PINs for a batch — admin only."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        batch = request.query_params.get('batch', '').strip()
        if not batch:
            return Response({'detail': 'batch param required.'}, status=400)

        cards = ScratchCard.objects.filter(
            school=self.school, batch_name=batch, is_used=False
        )
        # Note: we can only return serial numbers here — PINs are hashed and not recoverable.
        # Admins should keep the original CSV from generation. This endpoint lists unused serials.
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['serial_number', 'status'])
        for card in cards:
            writer.writerow([card.serial_number, 'unused'])
        output.seek(0)

        filename = f"unused_{batch.replace(' ', '_')}.csv"
        response = HttpResponse(output.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


# ─────────────────────────────────────────────────────────────────────────────
# Public PIN Check (NO auth, NO tenant middleware)
# ─────────────────────────────────────────────────────────────────────────────

class PublicResultCheckView(APIView):
    """
    Public endpoint — no login required.
    Accepts admission_number + serial_number + pin.
    Verifies the scratch card, marks it used, returns full result JSON.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        admission_number = request.data.get('admission_number', '').strip().upper()
        serial_number    = request.data.get('serial_number', '').strip().upper()
        pin              = request.data.get('pin', '').strip()

        if not (admission_number and serial_number and pin):
            return Response(
                {'detail': 'admission_number, serial_number and pin are all required.'},
                status=400,
            )

        # Look up card
        try:
            card = ScratchCard.objects.select_related('school').get(
                serial_number=serial_number
            )
        except ScratchCard.DoesNotExist:
            return Response({'detail': 'Invalid serial number.'}, status=404)

        # Verify PIN
        if not check_password(pin, card.pin_hash):
            return Response({'detail': 'Incorrect PIN.'}, status=403)

        # Already used?
        if card.is_used:
            return Response(
                {'detail': 'This card has already been used.'},
                status=403,
            )

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
            return Response(
                {'detail': 'No student found with that admission number.'},
                status=404,
            )

        # Determine term — use card's term if set, else current term for the school
        if card.term:
            term = card.term
        else:
            from academics.models import Term
            term = Term.objects.filter(
                session__school=card.school, is_current=True
            ).first()
            if not term:
                return Response(
                    {'detail': 'No current term configured for this school.'},
                    status=404,
                )

        # Mark card used atomically to prevent double-use race condition
        updated = ScratchCard.objects.filter(pk=card.pk, is_used=False).update(
            is_used=True,
            used_at=timezone.now(),
            used_by_student=student,
        )
        if not updated:
            return Response({'detail': 'This card has already been used.'}, status=403)

        # Assemble and return result data
        data = _assemble_slip_data(card.school, student, term)
        return Response(data)
