"""Restore missing platform offers without changing configured commercial terms."""
from django.core.management.base import BaseCommand
from django.db import transaction

from fees.models import SubscriptionOffer


# Canonical launch defaults from fees migration 0007; parity is regression-tested.
DEFAULT_OFFERS = (("basic", "800.00"), ("premium", "1500.00"), ("enterprise", "2500.00"))


class Command(BaseCommand):
    help = "Create missing platform subscription offers; preserve existing offers."

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        for plan, amount in DEFAULT_OFFERS:
            _, created = SubscriptionOffer.objects.get_or_create(
                plan=plan,
                defaults={"amount": amount, "months": 3, "enabled": True},
            )
            created_count += int(created)
        self.stdout.write(self.style.SUCCESS(
            f"Platform bootstrap complete: {created_count} offers created."
        ))
