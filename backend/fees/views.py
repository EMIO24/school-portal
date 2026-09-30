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
import hashlib
import re
from decimal import Decimal
from requests.exceptions import RequestException

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from accounts.permissions import IsSchoolAdmin, IsAuthenticatedTenantUser
from .access import payment_student, check_student_access
from enrollment.models import StudentProfile, ClassArm
from .models import FeeCategory, FeeSchedule, FeePayment
from .serializers import FeeCategorySerializer, FeeScheduleSerializer, FeePaymentSerializer
from .services.paystack import PaystackService
from .ledger import record_payment_entry, account_balance
from .models import StudentLedgerEntry, StudentPaymentAllocation
from tenants.document_branding import secure_document_response
from tenants.document_branding import receipt_barcode_data_uri, school_branding_context


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
    permission_classes = [IsAuthenticatedTenantUser]

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
    permission_classes = [IsAuthenticatedTenantUser]

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
        if FeePayment.objects.filter(fee_schedule__fee_category=obj).exists():
            return Response({'detail': 'This category has receipts and must be retained.'}, status=409)
        obj.delete()
        return Response(status=204)


# ── Schedule ──────────────────────────────────────────────────────────────────

def _fee_schedule_locked(schedule):
    from .models import PaymentOrder
    if FeePayment.objects.filter(fee_schedule=schedule).exists():
        return True
    if StudentLedgerEntry.objects.filter(fee_schedule=schedule).exists():
        return True
    for allocations in PaymentOrder.objects.filter(
            school=schedule.school, kind='fees').values_list('allocations', flat=True).iterator():
        if any(item.get('schedule_id') == schedule.pk for item in (allocations or []) if isinstance(item, dict)):
            return True
    return False


class FeeScheduleView(APIView):
    permission_classes = [IsAuthenticatedTenantUser]

    def get_permissions(self):
        return [IsSchoolAdmin()] if self.request.method == "POST" else super().get_permissions()

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

        from academics.models import Term
        from enrollment.models import ClassLevel
        if not Term.objects.filter(pk=term_id, session__school=school).exists():
            return Response({'error': 'Select a term belonging to this school.'}, status=400)
        if not isinstance(schedules, list):
            return Response({'error': 'Schedules must be a list.'}, status=400)
        created = []
        errors  = []
        for i, item in enumerate(schedules):
            try:
                if not ClassLevel.objects.filter(pk=item.get('class_level_id'), school=school).exists() or not FeeCategory.objects.filter(pk=item.get('fee_category_id'), school=school).exists():
                    raise ValueError('Class and fee category must belong to this school.')
                value = Decimal(str(item.get('amount')))
                if not value.is_finite() or value <= 0 or value != value.quantize(Decimal('0.01')):
                    raise ValueError('Enter a positive fee amount with at most two decimal places.')
                obj = FeeSchedule.objects.filter(
                    school=school,
                    term_id=term_id,
                    class_level_id=item['class_level_id'],
                    fee_category_id=item['fee_category_id'],
                ).first()
                proposed_due = item.get('due_date') or None
                if obj:
                    changed = obj.amount != value or str(obj.due_date or '') != str(proposed_due or '')
                    if changed and _fee_schedule_locked(obj):
                        raise ValueError(
                            'This fee schedule already has financial history. '
                            'Keep it unchanged and use a controlled adjustment or a later-term schedule.'
                        )
                    if changed:
                        obj.amount = value
                        obj.due_date = proposed_due
                        obj.save(update_fields=['amount', 'due_date'])
                else:
                    obj = FeeSchedule.objects.create(
                        school=school, term_id=term_id,
                        class_level_id=item['class_level_id'],
                        fee_category_id=item['fee_category_id'],
                        amount=value, due_date=proposed_due,
                    )
                created.append(obj.id)
            except (KeyError, Exception) as exc:
                errors.append({'index': i, 'detail': str(exc)})

        status_code = 207 if errors else 201
        return Response({'created': len(created), 'errors': errors}, status=status_code)


# ── Student fee summary ───────────────────────────────────────────────────────

class StudentFeesView(APIView):
    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request, pk):
        school  = getattr(request, 'tenant', None)
        term_id = request.query_params.get('term')
        if term_id and not re.fullmatch(r'[1-9][0-9]*', str(term_id)):
            return Response({'detail': 'Select a valid term.'}, status=400)

        try:
            student = payment_student(request, pk)
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

        position = account_balance(school, student)
        charges = {entry.fee_schedule_id: entry for entry in StudentLedgerEntry.objects.filter(
            school=school, student=student, kind='charge', fee_schedule__in=schedules)}
        applied = {row['charge__fee_schedule_id']: row['total'] for row in
            StudentPaymentAllocation.objects.filter(school=school, charge__student=student,
                charge__fee_schedule__in=schedules).values('charge__fee_schedule_id').annotate(total=Sum('amount'))}
        paid_allocations = {row['charge__fee_schedule_id']: row['total'] for row in
            StudentPaymentAllocation.objects.filter(school=school, charge__student=student,
                charge__fee_schedule__in=schedules, credit__kind='payment')
                .values('charge__fee_schedule_id').annotate(total=Sum('amount'))}

        result = []
        for sched in schedules:
            sched_payments = payments_by_sched.get(sched.id, [])
            paid = sum(p.amount_paid for p in sched_payments) or Decimal('0')
            charge = charges.get(sched.pk)
            result.append({
                'schedule':    FeeScheduleSerializer(sched).data,
                'amount':      charge.signed_amount if charge else sched.amount,
                'paid':        paid_allocations.get(sched.pk, Decimal('0')) if charge else paid,
                'credits':     applied.get(sched.pk, Decimal('0')) - paid_allocations.get(sched.pk, Decimal('0')) if charge else Decimal('0'),
                'outstanding': max(charge.signed_amount - applied.get(sched.pk, Decimal('0')), Decimal('0'))
                               if charge and position['state'] == 'active' else None,
                'charge_state': 'charged' if charge else 'not_generated',
                'finance_state': position['state'],
                'payments':    FeePaymentSerializer(sched_payments, many=True).data,
            })

        return Response(result)


# ── Paystack ──────────────────────────────────────────────────────────────────

from .payments import PaystackInitiateView, PaystackVerifyView


class ManualPaymentView(APIView):
    permission_classes = [IsSchoolAdmin]

    @transaction.atomic
    def post(self, request):
        from tenants.models import School
        school = School.objects.select_for_update().get(pk=request.tenant.pk)
        d      = request.data

        # Validate required fields before touching the DB
        required = ['student_id', 'fee_schedule_id', 'amount_paid', 'payment_date']
        missing  = [f for f in required if not d.get(f)]
        if missing:
            return Response({'error': f"Missing fields: {', '.join(missing)}"}, status=400)
        if any(isinstance(d[field], bool) or not re.fullmatch(r'[1-9][0-9]*', str(d[field]))
               for field in ('student_id', 'fee_schedule_id')):
            return Response({'error': 'Select a valid student and fee item.'}, status=400)

        # Tenant-scoped lookups guard against cross-school writes
        try:
            student  = StudentProfile.objects.get(pk=d['student_id'], school=school)
            schedule = FeeSchedule.objects.get(pk=d['fee_schedule_id'], school=school)
        except (StudentProfile.DoesNotExist, FeeSchedule.DoesNotExist) as exc:
            return Response({'error': str(exc)}, status=404)

        try:
            payment_date = parse_date(str(d['payment_date']))
        except (TypeError, ValueError):
            payment_date = None
        if payment_date is None:
            return Response({'error': 'payment_date must be a valid YYYY-MM-DD date.'}, status=400)

        if d.get('method', 'cash') not in ('cash', 'bank_transfer'):
            return Response({'error': 'Online payments must be verified through Paystack.'}, status=400)
        try:
            amount = Decimal(str(d['amount_paid']))
            if not amount.is_finite() or amount <= 0 or amount > Decimal('99999999.99') or amount != amount.quantize(Decimal('0.01')):
                raise ValueError()
        except Exception:
            return Response({'error': 'Enter a positive amount with at most two decimal places.'}, status=400)
        idempotency_key = str(d.get('idempotency_key', '')).strip()
        if idempotency_key and not re.fullmatch(r'[A-Za-z0-9._:-]{8,100}', idempotency_key):
            return Response({'error': 'Payment retry key is invalid. Reload the form and try again.'}, status=400)
        receipt_number = ''
        if idempotency_key:
            digest = hashlib.sha256(f'{school.pk}:{idempotency_key}'.encode()).hexdigest()[:20].upper()
            receipt_number = f'REC-IDEM-{digest}'
            existing = FeePayment.objects.filter(school=school, receipt_number=receipt_number).first()
            if existing:
                same_payment = (
                    existing.student_id == student.pk and existing.fee_schedule_id == schedule.pk
                    and existing.amount_paid == amount and existing.payment_date == payment_date
                    and existing.method == d.get('method', 'cash')
                )
                if not same_payment:
                    return Response({'error': 'This payment retry key was already used for different details.'}, status=409)
                return Response(FeePaymentSerializer(existing).data, status=200)
        charge = StudentLedgerEntry.objects.filter(school=school, student=student,
            fee_schedule=schedule, kind='charge').first()
        opening = StudentLedgerEntry.objects.filter(school=school, student=student, kind='opening').first()
        old_opening_period = bool(opening and schedule.term.start_date <= opening.effective_date)
        paid = FeePayment.objects.filter(student=student, fee_schedule=schedule).aggregate(total=Sum('amount_paid'))['total'] or Decimal(0)
        if charge:
            applied = charge.charge_allocations.aggregate(total=Sum('amount'))['total'] or Decimal(0)
            remaining = max(charge.signed_amount - applied, Decimal(0))
        elif old_opening_period:
            remaining = account_balance(school, student)['outstanding']
        else:
            remaining = schedule.amount - paid
        allow_credit = d.get('allow_credit') is True
        if (not charge and not old_opening_period and (not student.current_class or schedule.class_level_id != student.current_class.class_level_id)) or \
                (allow_credit and (not charge and not old_opening_period or account_balance(school, student)['state'] != 'active')) or \
                (not allow_credit and amount > remaining):
            return Response({'error': 'Payment must match a valid student charge and cannot exceed the outstanding amount unless account credit is explicitly selected.'}, status=400)
        payment = FeePayment(
            school=school,
            student=student,
            fee_schedule=schedule,
            amount_paid=amount,
            payment_date=payment_date,
            method=d.get('method', 'cash'),
            recorded_by=request.user,
            receipt_number=receipt_number,
        )
        payment.save()
        record_payment_entry(payment, key='manual:' + hashlib.sha256(idempotency_key.encode()).hexdigest()
                             if idempotency_key else '')
        return Response(FeePaymentSerializer(payment).data, status=201)


# ── Receipt PDF ───────────────────────────────────────────────────────────────

class FeeReceiptView(APIView):
    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request, pk):
        school = getattr(request, 'tenant', None)
        try:
            payment = FeePayment.objects.select_related(
                'student__user', 'fee_schedule__fee_category', 'school'
            ).get(pk=pk, school=school)
        except FeePayment.DoesNotExist:
            return Response(status=404)

        check_student_access(request.user, payment.student)
        try:
            from weasyprint import HTML
            receipt = payment.receipt_snapshot or payment._receipt_snapshot()
            contact = ' | '.join(filter(None, [
                receipt.get('school_address', ''), receipt.get('school_phone', ''), receipt.get('school_email', '')
            ]))
            html = render_to_string('fees/receipt.html', {
                'payment': payment,
                'receipt': receipt,
                'receipt_barcode': receipt_barcode_data_uri(payment),
                'school_name': receipt.get('school_name', ''),
                'school_logo': receipt.get('school_logo', ''),
                'school_motto': receipt.get('school_motto', ''),
                'school_contact_line': contact,
                'school_registration_number': receipt.get('school_registration_number', ''),
                'document_primary_color': receipt.get('document_primary_color', '#173B56'),
                'document_secondary_color': receipt.get('document_secondary_color', '#256D85'),
                'document_accent_color': receipt.get('document_accent_color', '#D8A548'),
            })
            pdf  = HTML(string=html).write_pdf()
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="{payment.receipt_number}.pdf"'
            return secure_document_response(resp)
        except Exception:
            receipt = payment.receipt_snapshot or payment._receipt_snapshot()
            pdf = _simple_pdf_bytes([
                receipt.get('school_name', 'School'),
                f'Receipt {payment.receipt_number}',
                f"Student: {receipt.get('student_name', '')}",
                f"Admission No: {receipt.get('admission_number', '')}",
                f"Class: {receipt.get('class_name', '')}",
                f"Category: {receipt.get('fee_category', '')}",
                f"Term: {receipt.get('term_name', '')} {receipt.get('session_name', '')}".strip(),
                f"Amount: {receipt.get('amount_paid', '')}",
            ])
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="{payment.receipt_number}.pdf"'
            return secure_document_response(resp)


# ── Outstanding fees ──────────────────────────────────────────────────────────

class OutstandingFeesView(APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        school = getattr(request, 'tenant', None)
        term_id = request.query_params.get('term')
        class_arm_id = request.query_params.get('class_arm')
        if term_id and not re.fullmatch(r'[1-9][0-9]*', str(term_id)):
            return Response({'detail': 'Select a valid term.'}, status=400)
        if class_arm_id and not re.fullmatch(r'[1-9][0-9]*', str(class_arm_id)):
            return Response({'detail': 'Select a valid class.'}, status=400)

        student_qs = StudentProfile.objects.filter(
            school=school, status='active'
        ).select_related('user', 'current_class__class_level')
        if class_arm_id:
            student_qs = student_qs.filter(current_class_id=class_arm_id)

        ledger = StudentLedgerEntry.objects.filter(school=school, student__in=student_qs)
        if term_id:
            ledger = ledger.filter(term_id=term_id)

        aggregates = {
            row['student_id']: row
            for row in ledger.values('student_id').annotate(
                charges=Sum('signed_amount', filter=Q(kind='charge')),
                payments=Sum('signed_amount', filter=Q(kind='payment')),
                balance=Sum('signed_amount'),
            )
        }

        summary_expected = sum((row['charges'] or Decimal('0')) for row in aggregates.values(), Decimal('0'))
        summary_collected = sum((abs(row['payments'] or Decimal('0'))) for row in aggregates.values(), Decimal('0'))
        summary_outstanding = sum(
            (max(row['balance'] or Decimal('0'), Decimal('0')) for row in aggregates.values()),
            Decimal('0'),
        )

        paginator = PageNumberPagination()
        paginator.page_size = 50
        student_list = paginator.paginate_queryset(student_qs, request, view=self)

        result = []
        for student in student_list:
            row = aggregates.get(student.pk, {})
            total = row.get('charges') or Decimal('0')
            paid = abs(row.get('payments') or Decimal('0'))
            outstanding = max(row.get('balance') or Decimal('0'), Decimal('0'))
            result.append({
                'student_id': student.id,
                'student_name': student.user.get_full_name() or student.admission_number,
                'class': student.current_class.full_name if student.current_class else '',
                'total_fees': total,
                'paid': paid,
                'outstanding': outstanding,
            })

        response = paginator.get_paginated_response(result)
        response.data['summary'] = {
            'total_expected': summary_expected,
            'total_collected': summary_collected,
            'total_outstanding': summary_outstanding,
        }
        return response

