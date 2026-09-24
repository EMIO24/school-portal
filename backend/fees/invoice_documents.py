import logging

from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework.exceptions import ValidationError

from results.report_pdf import text_report_pdf
from tenants.document_branding import secure_document_response


def invoice_document(invoice, *, receipt=False):
    if receipt and (invoice.status != 'paid' or not invoice.payment_id):
        raise ValidationError('A receipt is available only after verified payment.')
    number = 'RCP-' + invoice.invoice_number if receipt else invoice.invoice_number
    title = 'Payment receipt' if receipt else 'Subscription invoice'
    html = render_to_string('fees/subscription_invoice.html', {
        'invoice': invoice, 'receipt': receipt, 'number': number, 'title': title,
    })
    try:
        from weasyprint import HTML
        pdf = HTML(string=html).write_pdf()
    except (ImportError, OSError):
        logging.getLogger(__name__).warning('invoice_pdf_fallback invoice_id=%s', invoice.pk)
        lines = [invoice.school_name, number, f'{invoice.session_name} / {invoice.term_name}',
                 f'Plan: {invoice.plan} / {invoice.subscription_months or "Not confirmed"} months',
                 f'Active students: {invoice.active_student_count}', f'Standard rate: NGN {invoice.standard_rate}',
                 f'Discount: {invoice.discount_percentage}% / NGN {invoice.discount_amount}',
                 f'Effective rate: NGN {invoice.effective_rate}', f'Subtotal: NGN {invoice.subtotal}',
                 f'Total: NGN {invoice.final_amount}', f'Issued: {invoice.issue_date} / Due: {invoice.due_date}',
                 f'Status: {invoice.display_status}']
        if receipt:
            lines += [f'Paid: {invoice.paid_at}', f'Paystack reference: {invoice.payment.reference}']
        lines += ['Paideia portal subscription. Student tuition and school fees are separate.',
                  'Amounts reflect the billing record at issue time.']
        pdf = text_report_pdf('Paideia Portals - ' + title, lines)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{number}.pdf"'
    return secure_document_response(response)
