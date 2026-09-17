from django.db import migrations


def update_subscription_offers(apps, schema_editor):
    SubscriptionOffer = apps.get_model('fees', 'SubscriptionOffer')
    for plan, amount in [('basic', '1200.00'), ('premium', '2000.00')]:
        SubscriptionOffer.objects.filter(plan=plan).update(amount=amount, months=3, enabled=True)


class Migration(migrations.Migration):
    dependencies = [
        ('fees', '0005_protect_payment_student'),
    ]

    operations = [
        migrations.RunPython(update_subscription_offers, migrations.RunPython.noop),
    ]
