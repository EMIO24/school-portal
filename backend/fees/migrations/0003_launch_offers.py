from django.db import migrations


def seed(apps, schema_editor):
    Offer = apps.get_model('fees', 'SubscriptionOffer')
    for plan, amount in [('basic', '75000.00'), ('premium', '150000.00')]:
        Offer.objects.get_or_create(plan=plan, defaults={'amount': amount, 'months': 3, 'enabled': True})


class Migration(migrations.Migration):
    dependencies = [('fees', '0002_subscriptionoffer_schoolpaymentaccount_paymentorder_and_more')]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
