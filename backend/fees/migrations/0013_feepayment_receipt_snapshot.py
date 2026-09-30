from django.db import migrations, models


def backfill_receipt_snapshots(apps, schema_editor):
    Payment = apps.get_model('fees', 'FeePayment')
    alias = schema_editor.connection.alias
    rows = Payment.objects.using(alias).select_related(
        'school', 'student__user', 'student__current_class',
        'fee_schedule__fee_category', 'fee_schedule__term__session', 'recorded_by'
    ).filter(receipt_snapshot={}).iterator(chunk_size=500)
    for payment in rows:
        school = payment.school
        student = payment.student
        schedule = payment.fee_schedule
        theme = getattr(school, 'theme_config', {}) or {}
        actor = payment.recorded_by
        payment.receipt_snapshot = {
            'school_name': getattr(school, 'name', ''),
            'school_logo': getattr(school, 'logo', '') or '',
            'school_motto': getattr(school, 'motto', '') or '',
            'school_address': getattr(school, 'address', '') or '',
            'school_phone': getattr(school, 'phone', '') or '',
            'school_email': getattr(school, 'email', '') or '',
            'school_registration_number': getattr(school, 'registration_number', '') or '',
            'document_primary_color': theme.get('primary_color', '#173B56'),
            'document_secondary_color': theme.get('secondary_color', '#256D85'),
            'document_accent_color': theme.get('accent_color', '#D8A548'),
            'student_name': student.user.get_full_name() or student.admission_number,
            'admission_number': student.admission_number,
            'class_name': student.current_class.full_name if student.current_class_id else '',
            'fee_category': schedule.fee_category.name,
            'term_name': schedule.term.get_name_display(),
            'session_name': schedule.term.session.name,
            'amount_paid': str(payment.amount_paid),
            'payment_date': str(payment.payment_date),
            'method': payment.method,
            'method_label': dict([('cash','Cash'),('paystack','Paystack'),('bank_transfer','Bank Transfer')]).get(payment.method, payment.method),
            'paystack_reference': payment.paystack_reference or '',
            'issued_by': actor.get_full_name() if actor else 'School Admin',
        }
        payment.save(update_fields=['receipt_snapshot'])


class Migration(migrations.Migration):
    dependencies = [('fees', '0012_studentfinanceaccount_studentledgerentry_and_more')]
    operations = [
        migrations.AddField(
            model_name='feepayment',
            name='receipt_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(backfill_receipt_snapshots, migrations.RunPython.noop),
    ]
