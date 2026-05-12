"""
backend/fees/views.py

GET/POST /api/fees/categories/
GET/PUT/DELETE /api/fees/categories/{id}/
GET/POST /api/fees/schedule/
GET      /api/fees/student/{id}/?term=
POST     /api/fees/pay/initiate/
GET      /api/fees/pay/verify/?reference=
POST     /api/fees/pay/manual/
GET      /api/fees/receipts/{id}/
GET      /api/fees/outstanding/?term=&class_arm=
"""

import uuid
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Sum
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSchoolAdmin
from enrollment.models import StudentProfile, ClassArm
from .models import FeeCategory, FeeSchedule, FeePayment
from .serializers import FeeCategorySerializer, FeeScheduleSerializer, FeePaymentSerializer
from .services.paystack import PaystackService


def _simple_pdf_bytes(lines):
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


# ── Category CRUD ─────────────────────────────────────────────────────────────

class FeeCategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsSchoolAdmin()]
        return [permission() for permission in self.permission_classes]

    def get(self, request):
        school = getattr(request, 'tenant', None)
        qs     = FeeCategory.objects.filter(school=school)
        return Response(FeeCategorySerializer(qs, many=True).data)

    def post(self, request):
        school = getattr(request, 'tenant', None)
        ser    = FeeCategorySerializer(data=request.data)
        if ser.is_valid():
            ser.save(school=school)
            return Response(ser.data, status=201)
        return Response(ser.errors, status=400)


class FeeCategoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.request.method in ('PUT', 'DELETE'):
            return [IsSchoolAdmin()]
        return [permission() for permission in self.permission_classes]

    def _obj(self, pk, school):
        try:
            return FeeCategory.objects.get(pk=pk, school=school)
        except FeeCategory.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._obj(pk, getattr(request, 'tenant', None))
        return Response(FeeCategorySerializer(obj).data) if obj else Response(status=404)

    def put(self, request, pk):
        obj = self._obj(pk, getattr(request, 'tenant', None))
        if not obj:
            return Response(status=404)
        ser = FeeCategorySerializer(obj, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=400)

    def delete(self, request, pk):
        obj = self._obj(pk, getattr(request, 'tenant', None))
        if not obj:
            return Response(status=404)
        obj.delete()
        return Response(status=204)


# ── Schedule ──────────────────────────────────────────────────────────────────

class FeeScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school     = getattr(request, 'tenant', None)
        term_id    = request.query_params.get('term')
        level_id   = request.query_params.get('class_level')
        qs = FeeSchedule.objects.filter(school=school).select_related('fee_category', 'class_level', 'term__session')
        if term_id:
            qs = qs.filter(term_id=term_id)
        if level_id:
            qs = qs.filter(class_level_id=level_id)
        return Response(FeeScheduleSerializer(qs, many=True).data)

    def post(self, request):
        """Bulk create: {term_id, schedules:[{class_level_id, fee_category_id, amount, due_date?}]}"""
        school    = getattr(request, 'tenant', None)
        term_id   = request.data.get('term_id')
        schedules = request.data.get('schedules', [])

        created = []
        errors  = []
        for i, item in enumerate(schedules):
            try:
                obj, _ = FeeSchedule.objects.update_or_create(
                    school=school,
                    term_id=term_id,
                    class_level_id=item['class_level_id'],
                    fee_category_id=item['fee_category_id'],
                    defaults={
                        'amount':   item['amount'],
                        'due_date': item.get('due_date'),
                    },
                )
                created.append(obj.id)
            except (KeyError, Exception) as exc:
                errors.append({'index': i, 'detail': str(exc)})

        status_code = 207 if errors else 201
        return Response({'created': len(created), 'errors': errors}, status=status_code)


# ── Student fee summary ───────────────────────────────────────────────────────

class StudentFeesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        school  = getattr(request, 'tenant', None)
        term_id = request.query_params.get('term')

        try:
            student = StudentProfile.objects.get(pk=pk, school=school)
        except StudentProfile.DoesNotExist:
            return Response(status=404)

        schedules = list(FeeSchedule.objects.filter(
            school=school,
            class_level=student.current_class.class_level if student.current_class else None,
            **(({'term_id': term_id}) if term_id else {}),
        ).select_related('fee_category', 'term__session'))

        # Batch-fetch all payments for all schedules in one query
        all_payments = list(
            FeePayment.objects.filter(
                student=student, fee_schedule__in=schedules,
            ).select_related('student__user', 'fee_schedule__fee_category')
        )
        payments_by_sched = {}
        for p in all_payments:
            payments_by_sched.setdefault(p.fee_schedule_id, []).append(p)

        result = []
        for sched in schedules:
            sched_payments = payments_by_sched.get(sched.id, [])
            paid = sum(p.amount_paid for p in sched_payments) or Decimal('0')
            result.append({
                'schedule':    FeeScheduleSerializer(sched).data,
                'amount':      sched.amount,
                'paid':        paid,
                'outstanding': max(sched.amount - paid, Decimal('0')),
                'payments':    FeePaymentSerializer(sched_payments, many=True).data,
            })

        return Response(result)


# ── Paystack ──────────────────────────────────────────────────────────────────

class PaystackInitiateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school           = getattr(request, 'tenant', None)
        student_id       = request.data.get('student_id')
        fee_schedule_ids = request.data.get('fee_schedule_ids', [])

        try:
            student = StudentProfile.objects.get(pk=student_id, school=school)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=404)

        schedules = FeeSchedule.objects.filter(id__in=fee_schedule_ids, school=school)
        total_naira = schedules.aggregate(t=Sum('amount'))['t'] or Decimal('0')
        total_kobo  = int(total_naira * 100)

        reference = f"SCH-{uuid.uuid4().hex[:12].upper()}"
        email     = student.guardian_email or student.user.email
        callback  = request.build_absolute_uri(f'/api/fees/pay/verify/?reference={reference}')

        try:
            ps    = PaystackService()
            url, ref = ps.initialize(email, total_kobo, reference, callback)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=502)

        # Store pending payment in Redis cache (JWT clients don't send session cookies)
        cache.set(f'ps_pending:{ref}', {
            'student_id':       student.id,
            'fee_schedule_ids': fee_schedule_ids,
        }, timeout=3600)

        return Response({'authorization_url': url, 'reference': ref})


class PaystackVerifyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school    = getattr(request, 'tenant', None)
        reference = request.query_params.get('reference', '')

        try:
            ps   = PaystackService()
            data = ps.verify(reference)
        except ValueError as exc:
            return Response({'error': str(exc)}, status=502)

        if data.get('status') != 'success':
            return Response({'error': 'Payment not successful'}, status=400)

        pending = cache.get(f'ps_pending:{reference}')
        if not pending:
            return Response({'error': 'No pending payment found for this reference'}, status=404)
        cache.delete(f'ps_pending:{reference}')

        student    = StudentProfile.objects.get(pk=pending['student_id'], school=school)
        schedules  = FeeSchedule.objects.filter(id__in=pending['fee_schedule_ids'])
        created    = []
        for sched in schedules:
            p = FeePayment.objects.create(
                school=school,
                student=student,
                fee_schedule=sched,
                amount_paid=sched.amount,
                payment_date=timezone.now().date(),
                method='paystack',
                paystack_reference=reference,
                paystack_status='success',
            )
            created.append(p.receipt_number)

        return Response({'status': 'success', 'receipts': created})


# ── Manual payment ────────────────────────────────────────────────────────────

class ManualPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school = getattr(request, 'tenant', None)
        d      = request.data

        # Validate required fields before touching the DB
        required = ['student_id', 'fee_schedule_id', 'amount_paid', 'payment_date']
        missing  = [f for f in required if not d.get(f)]
        if missing:
            return Response({'error': f"Missing fields: {', '.join(missing)}"}, status=400)

        # Tenant-scoped lookups guard against cross-school writes
        try:
            student  = StudentProfile.objects.get(pk=d['student_id'], school=school)
            schedule = FeeSchedule.objects.get(pk=d['fee_schedule_id'], school=school)
        except (StudentProfile.DoesNotExist, FeeSchedule.DoesNotExist) as exc:
            return Response({'error': str(exc)}, status=404)

        payment_date = parse_date(str(d['payment_date']))
        if payment_date is None:
            return Response({'error': 'payment_date must be a valid YYYY-MM-DD date.'}, status=400)

        payment = FeePayment(
            school=school,
            student=student,
            fee_schedule=schedule,
            amount_paid=d['amount_paid'],
            payment_date=payment_date,
            method=d.get('method', 'cash'),
            recorded_by=request.user,
        )
        payment.save()
        return Response(FeePaymentSerializer(payment).data, status=201)


# ── Receipt PDF ───────────────────────────────────────────────────────────────

class FeeReceiptView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        school = getattr(request, 'tenant', None)
        try:
            payment = FeePayment.objects.select_related(
                'student__user', 'fee_schedule__fee_category', 'school'
            ).get(pk=pk, school=school)
        except FeePayment.DoesNotExist:
            return Response(status=404)

        try:
            from weasyprint import HTML
            html = render_to_string('fees/receipt.html', {'payment': payment, 'school': school})
            pdf  = HTML(string=html).write_pdf()
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="{payment.receipt_number}.pdf"'
            return resp
        except Exception:
            pdf = _simple_pdf_bytes([
                f'Receipt {payment.receipt_number}',
                f'Student: {payment.student.user.full_name or payment.student.admission_number}',
                f'Category: {payment.fee_schedule.fee_category.name}',
                f'Amount: {payment.amount_paid}',
            ])
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="{payment.receipt_number}.pdf"'
            return resp


# ── Outstanding fees ──────────────────────────────────────────────────────────

class OutstandingFeesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school       = getattr(request, 'tenant', None)
        term_id      = request.query_params.get('term')
        class_arm_id = request.query_params.get('class_arm')

        student_qs = StudentProfile.objects.filter(school=school, status='active').select_related(
            'user', 'current_class__class_level'
        )
        if class_arm_id:
            student_qs = student_qs.filter(current_class_id=class_arm_id)
        student_list = list(student_qs)

        # Collect distinct class_level ids to batch-fetch all matching schedules
        level_ids = list({
            s.current_class.class_level_id
            for s in student_list if s.current_class
        })

        sched_qs = FeeSchedule.objects.filter(school=school, class_level_id__in=level_ids)
        if term_id:
            sched_qs = sched_qs.filter(term_id=term_id)

        # Total fee amount per class_level — one query
        level_totals = {
            row['class_level_id']: row['t'] or Decimal('0')
            for row in sched_qs.values('class_level_id').annotate(t=Sum('amount'))
        }

        # Paid amount per student — one query
        student_ids = [s.id for s in student_list if s.current_class]
        paid_map = {
            row['student_id']: row['t'] or Decimal('0')
            for row in FeePayment.objects.filter(
                student_id__in=student_ids,
                fee_schedule__in=sched_qs,
            ).values('student_id').annotate(t=Sum('amount_paid'))
        }

        result = []
        for student in student_list:
            if not student.current_class:
                continue
            level_id = student.current_class.class_level_id
            total    = level_totals.get(level_id, Decimal('0'))
            paid     = paid_map.get(student.id, Decimal('0'))
            result.append({
                'student_id':   student.id,
                'student_name': student.user.get_full_name() or student.admission_number,
                'class':        student.current_class.full_name,
                'total_fees':   total,
                'paid':         paid,
                'outstanding':  max(total - paid, Decimal('0')),
            })

        return Response(result)
