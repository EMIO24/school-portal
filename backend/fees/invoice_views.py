from collections.abc import Mapping

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSchoolAdmin, IsSuperAdmin
from .invoices import issue_invoice, void_invoice
from .models import SubscriptionOffer, TermInvoice


class InvoiceSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source='display_status')
    receipt_number = serializers.SerializerMethodField()
    payment_reference = serializers.SerializerMethodField()

    def get_receipt_number(self, invoice):
        return 'RCP-' + invoice.invoice_number if invoice.status == 'paid' and invoice.payment_id else None

    def get_payment_reference(self, invoice):
        return invoice.payment.reference if invoice.payment_id else None

    class Meta:
        model = TermInvoice
        fields = ['id', 'invoice_number', 'school', 'school_name', 'academic_session', 'session_name',
                  'term', 'term_name', 'billing_context', 'plan', 'active_student_count', 'snapshot_at',
                  'standard_rate', 'discount_applied', 'discount_percentage', 'discount_amount',
                  'effective_rate', 'subtotal', 'final_amount', 'currency', 'issue_date', 'due_date',
                  'grace_period_days', 'status', 'paid_at', 'voided_at', 'void_reason',
                  'subscription_months', 'receipt_number', 'payment_reference']
        read_only_fields = fields


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping) and set(data) - set(self.fields):
            raise ValidationError({'non_field_errors': ['Unsupported fields. Invoice amounts and statuses are not directly editable.']})
        return super().to_internal_value(data)


class InvoiceFilters(StrictInput):
    plan = serializers.ChoiceField(choices=SubscriptionOffer._meta.get_field('plan').choices, required=False)
    academic_session = serializers.IntegerField(min_value=1, required=False)
    term = serializers.IntegerField(min_value=1, required=False)
    status = serializers.ChoiceField(choices=['issued', 'overdue', 'paid', 'void'], required=False)
    page = serializers.IntegerField(min_value=1, required=False)


class OwnerInvoiceFilters(InvoiceFilters):
    school = serializers.IntegerField(min_value=1, required=False)


class IssueInput(StrictInput):
    school = serializers.IntegerField(min_value=1)
    term = serializers.IntegerField(min_value=1)
    due_date = serializers.DateField()
    grace_period_days = serializers.IntegerField(min_value=0, max_value=365, default=0)


class VoidInput(StrictInput):
    action = serializers.ChoiceField(choices=['void'])
    reason = serializers.CharField(max_length=500)


class DurationInput(StrictInput):
    action = serializers.ChoiceField(choices=['set_duration'])
    months = serializers.IntegerField(min_value=1, max_value=12)


class InvoicePagination(PageNumberPagination):
    page_size = 50


class SchoolInvoices(APIView):
    permission_classes = [IsSchoolAdmin]
    filters = InvoiceFilters

    def invoices(self, request):
        return TermInvoice.objects.filter(school=request.tenant).select_related('payment')

    def get(self, request, pk=None):
        invoices = self.invoices(request)
        if pk is not None:
            invoice = get_object_or_404(invoices, pk=pk)
            data = dict(InvoiceSerializer(invoice).data)
            from .payments import result
            data['payment_attempts'] = [result(order) for order in invoice.payment_attempts.order_by('-id')[:30]]
            return Response(data)
        form = self.filters(data=request.query_params)
        form.is_valid(raise_exception=True)
        values = dict(form.validated_data)
        values.pop('page', None)
        status = values.pop('status', None)
        invoices = invoices.filter(**values)
        if status == 'overdue':
            invoices = invoices.filter(status='issued', due_date__lt=timezone.localdate())
        elif status == 'issued':
            invoices = invoices.filter(status='issued', due_date__gte=timezone.localdate())
        elif status:
            invoices = invoices.filter(status=status)
        paginator = InvoicePagination()
        rows = paginator.paginate_queryset(invoices, request, view=self)
        return paginator.get_paginated_response(InvoiceSerializer(rows, many=True).data)


class OwnerInvoices(SchoolInvoices):
    permission_classes = [IsSuperAdmin]
    filters = OwnerInvoiceFilters

    def invoices(self, request):
        return TermInvoice.objects.select_related('payment')

    def post(self, request, pk=None):
        if pk is not None:
            if request.data.get('action') == 'set_duration':
                from .invoice_payments import assign_legacy_duration
                form = DurationInput(data=request.data)
                form.is_valid(raise_exception=True)
                invoice = assign_legacy_duration(pk, months=form.validated_data['months'], actor=request.user)
                return Response(InvoiceSerializer(invoice).data)
            form = VoidInput(data=request.data)
            form.is_valid(raise_exception=True)
            invoice = void_invoice(pk, actor=request.user, reason=form.validated_data['reason'])
            return Response(InvoiceSerializer(invoice).data)
        form = IssueInput(data=request.data)
        form.is_valid(raise_exception=True)
        values = form.validated_data
        invoice, created = issue_invoice(school_id=values['school'], term_id=values['term'],
                                        due_date=values['due_date'], grace_period_days=values['grace_period_days'],
                                        actor=request.user)
        return Response(InvoiceSerializer(invoice).data, status=201 if created else 200)


class SchoolInvoiceDocument(SchoolInvoices):
    def get(self, request, pk, document):
        from .invoice_documents import invoice_document
        invoice = get_object_or_404(self.invoices(request), pk=pk)
        return invoice_document(invoice, receipt=document == 'receipt')


class OwnerInvoiceDocument(SchoolInvoiceDocument):
    permission_classes = [IsSuperAdmin]

    def invoices(self, request):
        return TermInvoice.objects.select_related('payment')
