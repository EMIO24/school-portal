"""Bounded school-fee ledger APIs. No background worker or mutable entry endpoint."""
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSchoolAdmin, IsAuthenticatedTenantUser
from academics.models import AcademicSession, Term
from enrollment.models import ClassArm, StudentProfile
from .access import payment_student
from .ledger import account_balance, balance_accounts, generate_charges, money, post_adjustment
from .models import FeePayment, FeeSchedule, StudentFinanceAccount, StudentLedgerEntry


class LedgerPages(PageNumberPagination):
    page_size = 50


def positive_id(value):
    if isinstance(value, bool):
        raise ValidationError({'detail': 'Select a valid record in this school.'})
    try:
        pk = int(value)
    except (TypeError, ValueError, OverflowError):
        raise ValidationError({'detail': 'Select a valid record in this school.'})
    if pk <= 0 or str(pk) != str(value):
        raise ValidationError({'detail': 'Select a valid record in this school.'})
    return pk


class StudentLedger(APIView):
    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request, pk):
        student = payment_student(request, pk)
        school = request.tenant
        position = account_balance(school, student)
        entries = StudentLedgerEntry.objects.filter(school=school, student=student).order_by('id')
        pager = LedgerPages()
        page = pager.paginate_queryset(entries, request)
        prior = StudentLedgerEntry.objects.filter(school=school, student=student,
            id__lt=page[0].id).aggregate(total=Sum('signed_amount'))['total'] if page else None
        running = prior or Decimal('0.00')
        rows = []
        for item in page:
            running += item.signed_amount
            rows.append({'id': item.pk, 'kind': item.kind, 'description': item.description,
                'amount': str(item.signed_amount), 'running_balance': str(running),
                'reason': item.reason if request.user.role == 'school_admin' else '',
                'reference': item.reference if request.user.role == 'school_admin' else '',
                'effective_date': item.effective_date,
                'recorded_at': item.created_at, 'term_id': item.term_id,
                'fee_schedule_id': item.fee_schedule_id,
                'receipt_id': item.fee_payment_id,
                'due_date': item.due_date_snapshot,
                'class_name': item.class_name_snapshot})
        legacy = list(FeePayment.objects.filter(school=school, student=student,
            ledger_entry__isnull=True).order_by('-payment_date', '-pk')
            .values('id', 'receipt_number', 'amount_paid', 'payment_date', 'method')[:50])
        response = pager.get_paginated_response(rows)
        response.data.update({'state': position['state'],
            'student_name': student.user.full_name,
            'balance': str(position['balance']) if position['balance'] is not None else None,
            'outstanding': str(position['outstanding']) if position['outstanding'] is not None else None,
            'credit': str(position['credit']) if position['credit'] is not None else None,
            'legacy_receipts': legacy,
            'legacy_receipts_note': 'Older receipts are genuine; their original charges are not known from current fee schedules.' if legacy else ''})
        return response


class ChargeGeneration(APIView):
    permission_classes = [IsSchoolAdmin]

    def post(self, request):
        school = request.tenant
        term = get_object_or_404(Term, pk=positive_id(request.data.get('term_id')), session__school=school)
        class_arm = None
        if request.data.get('class_arm_id') is not None:
            class_arm = get_object_or_404(ClassArm, pk=positive_id(request.data['class_arm_id']), school=school)
        try:
            return Response(generate_charges(school, term, request.user, class_arm=class_arm))
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)


class FinancialChange(APIView):
    permission_classes = [IsSchoolAdmin]

    def post(self, request):
        school = request.tenant
        student = get_object_or_404(StudentProfile, pk=positive_id(request.data.get('student_id')), school=school)
        term = None
        schedule = None
        if request.data.get('term_id') is not None:
            term = get_object_or_404(Term, pk=positive_id(request.data['term_id']), session__school=school)
        if request.data.get('fee_schedule_id') is not None:
            schedule = get_object_or_404(FeeSchedule, pk=positive_id(request.data['fee_schedule_id']), school=school,
                                         term__session__school=school)
            if term and schedule.term_id != term.pk:
                return Response({'detail': 'Fee structure does not belong to this term.'}, status=400)
        try:
            entry, created = post_adjustment(school, student, request.user,
                kind=request.data.get('kind'), amount=request.data.get('amount'),
                reason=request.data.get('reason'), key=request.data.get('idempotency_key'),
                term=term, schedule=schedule, reference=request.data.get('reference', ''),
                effective_date=request.data.get('effective_date'))
        except ValueError as exc:
            code = 409 if 'retry key was used' in str(exc) else 400
            return Response({'detail': str(exc)}, status=code)
        return Response({'id': entry.pk, 'kind': entry.kind, 'amount': str(entry.signed_amount),
            'state': account_balance(school, student)['state'],
            'replayed': not created}, status=201 if created else 200)


class LedgerAccounts(APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        school = request.tenant
        students = StudentProfile.objects.filter(school=school, status='active')
        arm_id = request.query_params.get('class_arm')
        if arm_id:
            if not ClassArm.objects.filter(school=school, pk=positive_id(arm_id)).exists():
                return Response({'detail': 'Select a class in this school.'}, status=400)
            students = students.filter(current_class_id=positive_id(arm_id))
        term_id = request.query_params.get('term')
        if term_id and not Term.objects.filter(session__school=school, pk=positive_id(term_id)).exists():
            return Response({'detail': 'Select a term in this school.'}, status=400)
        search = request.query_params.get('search', '').strip()[:80]
        if search:
            students = students.filter(Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) | Q(admission_number__icontains=search))
        known = balance_accounts(school, students)
        account_totals = known.aggregate(total_outstanding=Sum('balance', filter=Q(balance__gt=0)),
            total_credit=Sum('balance', filter=Q(balance__lt=0)),
            known_count=Count('pk'), debtor_count=Count('pk', filter=Q(balance__gt=0)))
        entry_totals = StudentLedgerEntry.objects.filter(school=school, student__in=students).aggregate(
            debits=Sum('signed_amount', filter=Q(signed_amount__gt=0)),
            payments=Sum('signed_amount', filter=Q(kind='payment')))
        rows = students.select_related('user', 'current_class__class_level', 'finance_account').annotate(
            ledger_balance=Sum('ledger_entries__signed_amount', filter=Q(ledger_entries__school=school)),
            charge_total=Sum('ledger_entries__signed_amount', filter=Q(ledger_entries__school=school,
                ledger_entries__signed_amount__gt=0)),
            payment_total=Sum('ledger_entries__signed_amount', filter=Q(ledger_entries__school=school,
                ledger_entries__kind='payment'))).order_by('user__last_name', 'pk')
        pager = LedgerPages()
        page = pager.paginate_queryset(rows, request)
        student_count = pager.page.paginator.count
        legacy_ids = set(FeePayment.objects.filter(school=school, student__in=page,
            ledger_entry__isnull=True).values_list('student_id', flat=True))
        result = []
        for student in page:
            account = getattr(student, 'finance_account', None)
            state = 'active' if account and account.state == 'active' and student.ledger_balance is not None \
                else 'legacy_review' if (account and account.state == 'legacy_review') or student.pk in legacy_ids else 'uninitialized'
            result.append({'student_id': student.pk, 'student_name': student.user.full_name,
                'class': student.current_class.full_name if student.current_class else '',
                'state': state, 'outstanding': max(student.ledger_balance, Decimal('0.00')) if state == 'active' else None,
                'credit': max(-student.ledger_balance, Decimal('0.00')) if state == 'active' else None,
                'total_fees': student.charge_total if state == 'active' else None,
                'paid': -student.payment_total if state == 'active' and student.payment_total else Decimal('0.00') if state == 'active' else None})
        response = pager.get_paginated_response(result)
        response.data['summary'] = {'total_expected': entry_totals['debits'] or Decimal('0.00'),
            'total_collected': -(entry_totals['payments'] or Decimal('0.00')),
            'total_outstanding': account_totals['total_outstanding'] or Decimal('0.00'),
            'total_credit': -(account_totals['total_credit'] or Decimal('0.00')),
            'unknown_accounts': student_count - account_totals['known_count'],
            'debtor_count': account_totals['debtor_count'],
            'scope': 'Whole student accounts; term chooses the charge-generation context.'}
        return response


class LedgerDebtors(APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        school = request.tenant
        students = StudentProfile.objects.filter(school=school, status='active')
        search = request.query_params.get('search', '').strip()[:80]
        if search:
            students = students.filter(Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) | Q(admission_number__icontains=search))
        arm_id = request.query_params.get('class_arm')
        if arm_id:
            if not ClassArm.objects.filter(school=school, pk=positive_id(arm_id)).exists():
                return Response({'detail': 'Select a class in this school.'}, status=400)
            students = students.filter(current_class_id=positive_id(arm_id))
        term_id = request.query_params.get('term')
        session_id = request.query_params.get('session')
        if session_id and not AcademicSession.objects.filter(school=school, pk=positive_id(session_id)).exists():
            return Response({'detail': 'Select a session in this school.'}, status=400)
        if term_id:
            if not Term.objects.filter(session__school=school, pk=positive_id(term_id),
                    **({'session_id': positive_id(session_id)} if session_id else {})).exists():
                return Response({'detail': 'Select a term in this school.'}, status=400)
            student_ids = StudentLedgerEntry.objects.filter(school=school, term_id=positive_id(term_id)).values_list('student_id', flat=True)
            students = students.filter(pk__in=student_ids)
        elif session_id:
            student_ids = StudentLedgerEntry.objects.filter(school=school,
                term__session_id=positive_id(session_id)).values_list('student_id', flat=True)
            students = students.filter(pk__in=student_ids)
        try:
            minimum = money(request.query_params.get('min_outstanding', '0'), allow_zero=True)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        known = balance_accounts(school, students)
        unknown_count = students.count() - known.count()
        debtors = known.filter(balance__gt=minimum).select_related('student__user',
            'student__current_class__class_level').order_by('student__user__last_name', 'student_id')
        total_outstanding = debtors.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        credited = known.filter(balance__lt=0).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        charges = StudentLedgerEntry.objects.filter(school=school, student__in=students,
            kind__in=('charge', 'opening', 'adjustment'), signed_amount__gt=0)
        payments = StudentLedgerEntry.objects.filter(school=school, student__in=students, kind='payment')
        total_charges = charges.aggregate(total=Sum('signed_amount'))['total'] or Decimal('0.00')
        total_paid = -(payments.aggregate(total=Sum('signed_amount'))['total'] or Decimal('0.00'))
        pager = LedgerPages()
        page = pager.paginate_queryset(debtors, request)
        result = [{'student_id': a.student_id, 'student_name': a.student.user.full_name,
            'class': a.student.current_class.full_name if a.student.current_class else '',
            'outstanding': a.balance, 'total_fees': None, 'paid': None,
            'state': 'active'} for a in page]
        response = pager.get_paginated_response(result)
        response.data['summary'] = {'total_expected': total_charges, 'total_collected': total_paid,
            'total_outstanding': total_outstanding, 'total_credit': -credited,
            'unknown_accounts': unknown_count, 'debtor_count': debtors.count(),
            'scope': 'Whole student account; term filter selects accounts with activity in that term.'}
        return response
