"""Operational cases only: no money movement or financial ledger mutation."""
from decimal import Decimal

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSchoolAdmin, IsSuperAdmin
from tenants.models import PlatformEvent
from tenants.security import audit
from .models import PaymentException, PaymentOrder


class CaseInput(serializers.Serializer):
    reference = serializers.CharField(max_length=100)
    kind = serializers.ChoiceField(choices=PaymentException.TYPES)
    reason = serializers.CharField(max_length=2000)


class ReviewInput(serializers.Serializer):
    expected_status = serializers.ChoiceField(choices=PaymentException.STATES)
    status = serializers.ChoiceField(choices=PaymentException.STATES)
    admin_notes = serializers.CharField(max_length=2000)
    provider_ref = serializers.CharField(max_length=100, required=False, allow_blank=True)


def validated(form_class, data):
    form = form_class(data=data)
    if set(data) - set(form.fields):
        raise ValidationError('Unsupported fields. Amounts and payment edits are not accepted.')
    form.is_valid(raise_exception=True)
    return form.validated_data


def record(request, case, previous):
    audit(request, 'payment.exception', f'payment_exception:{case.pk}', {
        'school_id': case.school_id, 'case_id': case.pk, 'order_id': case.order_id,
        'previous_status': previous, 'status': case.status,
        'admin_notes': case.admin_notes, 'provider_ref': case.provider_ref,
    })


def representation(case, internal=False, history=False):
    order = case.order
    data = {'id': case.pk, 'school_id': case.school_id, 'reference': order.reference,
            'kind': case.kind, 'status': case.status, 'reason': case.reason,
            'created_at': case.created_at, 'updated_at': case.updated_at,
            'resolved_at': case.resolved_at}
    if internal:
        data.update(admin_notes=case.admin_notes, provider_ref=case.provider_ref,
                    created_by=case.created_by_id, reviewed_by=case.reviewed_by_id,
                    payment={'status': order.status, 'provider_id': order.provider_id,
                             'payer_id': order.payer_id, 'student_id': order.student_id,
                             'amount': str(Decimal(order.amount_kobo) / 100),
                             'currency': order.currency, 'mode': order.mode, 'kind': order.kind,
                             'plan': order.plan, 'allocations': order.allocations,
                             'created_at': order.created_at, 'paid_at': order.paid_at})
        if history:
            data['history'] = list(PlatformEvent.objects.filter(action='payment.exception',
                target=f'payment_exception:{case.pk}').order_by('id').values('actor_id', 'created_at', 'details'))
    return data


class SchoolPaymentExceptions(APIView):
    permission_classes = [IsSchoolAdmin]
    internal = False

    def orders(self, request):
        orders = PaymentOrder.objects.all()
        return orders if self.internal else orders.filter(school=request.tenant)

    def cases(self, request):
        return PaymentException.objects.filter(order__in=self.orders(request)).select_related('order')

    def get(self, request, pk=None):
        cases = self.cases(request)
        if pk is not None:
            return Response(representation(get_object_or_404(cases, pk=pk), self.internal, history=True))
        for name, choices in (('status', PaymentException.STATES), ('kind', PaymentException.TYPES)):
            value = request.query_params.get(name)
            if value:
                if value not in dict(choices):
                    raise ValidationError(f'Invalid {name}.')
                cases = cases.filter(**{name: value})
        if request.query_params.get('reference'):
            cases = cases.filter(order__reference=request.query_params['reference'])
        # Cursor pagination keeps older cases reachable without unbounded lists.
        before = request.query_params.get('before')
        if before:
            try:
                cases = cases.filter(pk__lt=int(before))
            except ValueError:
                raise ValidationError('Invalid cursor.')
        rows = list(cases[:101])
        return Response({'results': [representation(c, self.internal) for c in rows[:100]],
                         'next_before': rows[99].pk if len(rows) > 100 else None})

    @transaction.atomic
    def post(self, request, pk=None):
        if pk is not None:
            raise ValidationError('Create cases through the collection endpoint.')
        values = validated(CaseInput, request.data)
        order = get_object_or_404(self.orders(request).select_for_update(), reference=values['reference'])
        existing = PaymentException.objects.filter(order=order, kind=values['kind']).first()
        if existing:
            if existing.reason != values['reason']:
                return Response({'detail': 'A case of this type already exists for this payment.', 'id': existing.pk}, status=409)
            return Response(representation(existing, self.internal))
        if values['kind'] == 'refund' and order.status != 'success':
            raise ValidationError('Verify and reconcile the payment first, or open a manual/provider review case.')
        case = PaymentException.objects.create(order=order, school=order.school, kind=values['kind'],
                                               reason=values['reason'], created_by=request.user)
        record(request, case, None)
        return Response(representation(case, self.internal), status=201)


class PlatformPaymentExceptions(SchoolPaymentExceptions):
    permission_classes = [IsSuperAdmin]
    internal = True

    @transaction.atomic
    def patch(self, request, pk=None):
        if pk is None:
            raise ValidationError('Select a case to review.')
        values = validated(ReviewInput, request.data)
        case = get_object_or_404(self.cases(request).select_for_update(), pk=pk)
        target = values['status']
        provider_ref = values.get('provider_ref', '')
        if (target == case.status and values['admin_notes'] == case.admin_notes
                and provider_ref == case.provider_ref):
            return Response(representation(case, True, history=True))
        if values['expected_status'] != case.status:
            return Response({'detail': 'Case changed. Reload before reviewing.'}, status=409)
        transitions = {'requested': {'under_review'}, 'under_review': {'rejected', 'resolved'},
                       'approved': {'provider_pending'}, 'provider_pending': {'provider_failed', 'resolved'},
                       'provider_failed': {'provider_pending'}}
        if case.kind == 'refund':
            transitions['under_review'] = {'approved', 'rejected'}
        else:
            transitions = {'requested': {'under_review'}, 'under_review': {'resolved'}}
        terminal = case.status in ('resolved', 'rejected')
        if terminal or (target != case.status and target not in transitions.get(case.status, set())):
            raise ValidationError('Invalid case transition.')
        if case.kind == 'refund' and target == 'approved' and case.order.status != 'success':
            raise ValidationError('A refund decision requires a verified successful payment.')
        if case.kind == 'refund' and target == 'resolved' and not provider_ref:
            raise ValidationError('Record an independently confirmed provider refund reference before resolving.')
        if provider_ref and not (case.kind == 'refund' and target == 'resolved'):
            raise ValidationError('Provider refund references are only recorded on confirmed resolution.')
        previous = case.status
        case.status, case.admin_notes = target, values['admin_notes']
        case.provider_ref = provider_ref
        case.reviewed_by = request.user
        if target in ('resolved', 'rejected'):
            case.resolved_at = timezone.now()
        case.save()
        record(request, case, previous)
        return Response(representation(case, True, history=True))
