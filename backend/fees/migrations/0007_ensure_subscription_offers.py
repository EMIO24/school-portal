from django.db import migrations


def ensure_subscription_offers(apps, schema_editor):
    SubscriptionOffer = apps.get_model("fees", "SubscriptionOffer")

    offers = [
        ("basic", "800.00"),
        ("premium", "1500.00"),
    ]

    for plan, amount in offers:
        SubscriptionOffer.objects.update_or_create(
            plan=plan,
            defaults={
                "amount": amount,
                "months": 3,
                "enabled": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("fees", "0006_refresh_subscription_offers"),
    ]

    operations = [
        migrations.RunPython(
            ensure_subscription_offers,
            migrations.RunPython.noop,
        ),
    ]
