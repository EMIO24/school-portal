from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('fees', '0013_feepayment_receipt_snapshot')]

    operations = [
        migrations.AddField(
            model_name='paymentorder',
            name='request_key',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddConstraint(
            model_name='paymentorder',
            constraint=models.UniqueConstraint(
                fields=('school', 'request_key'),
                condition=~models.Q(request_key=''),
                name='unique_school_payment_order_request_key',
            ),
        ),
    ]
