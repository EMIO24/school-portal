from importlib import import_module
from io import StringIO
from unittest.mock import patch
import os
from pathlib import Path
import shutil
import subprocess

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import DatabaseError
from django.test import SimpleTestCase, TestCase

from fees.models import PaymentOrder, SubscriptionOffer
from tenants.models import School


class PlatformBootstrapTests(TestCase):
    def setUp(self):
        # Only the disposable test database: simulate offers lost with history intact.
        SubscriptionOffer.objects.all().delete()

    def bootstrap(self):
        call_command("bootstrap_platform", stdout=StringIO())

    def offers(self):
        return list(SubscriptionOffer.objects.order_by("plan").values(
            "plan", "amount", "months", "enabled"
        ))

    def test_empty_bootstrap_matches_canonical_migration_without_customer_data(self):
        migration = import_module("fees.migrations.0007_ensure_subscription_offers")
        migration.ensure_subscription_offers(apps, None)
        expected = self.offers()
        SubscriptionOffer.objects.all().delete()
        self.bootstrap()
        self.assertEqual(self.offers(), expected)
        self.assertEqual(SubscriptionOffer.objects.count(), 2)
        self.assertFalse(School.objects.exists())
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(PaymentOrder.objects.exists())

    def test_repeated_bootstrap_preserves_ids_and_values(self):
        self.bootstrap()
        before = list(SubscriptionOffer.objects.order_by("plan").values())
        self.bootstrap()
        self.assertEqual(list(SubscriptionOffer.objects.order_by("plan").values()), before)

    def test_existing_configuration_preserved_and_missing_offer_restored(self):
        offer = SubscriptionOffer.objects.create(
            plan="premium", amount="1750.00", months=6, enabled=False
        )
        self.bootstrap()
        offer.refresh_from_db()
        self.assertEqual(str(offer.amount), "1750.00")
        self.assertEqual(offer.months, 6)
        self.assertFalse(offer.enabled)
        self.assertTrue(SubscriptionOffer.objects.filter(plan="basic").exists())

    def test_failure_propagates_and_rolls_back_partial_bootstrap(self):
        original = SubscriptionOffer.objects.get_or_create

        def fail_second(**kwargs):
            if kwargs["plan"] == "premium":
                raise DatabaseError("simulated bootstrap failure")
            return original(**kwargs)

        output = StringIO()
        with patch.object(SubscriptionOffer.objects, "get_or_create", side_effect=fail_second):
            with self.assertRaisesMessage(DatabaseError, "simulated bootstrap failure"):
                call_command("bootstrap_platform", stdout=output)
        self.assertFalse(SubscriptionOffer.objects.exists())
        self.assertNotIn("complete", output.getvalue())


class ResetEntrypointTests(SimpleTestCase):
    def run_entrypoint(self, reset="true", fail_bootstrap=False):
        git_bash = Path("C:/Program Files/Git/bin/bash.exe")
        bash = str(git_bash) if git_bash.exists() else shutil.which("bash")
        self.assertIsNotNone(bash, "Bash is required to verify the deployment entrypoint")
        # Execute the actual shell control flow with inert command substitutes.
        # No Python, Gunicorn, database or provider command can execute here.
        harness = '''
python() {
    echo "COMMAND:$2"
    if [ "$2" = "shell" ]; then while IFS= read -r line; do :; done; fi
    if [ "$2" = "bootstrap_platform" ] && [ "$FAIL_BOOTSTRAP" = "yes" ]; then
        echo "simulated bootstrap failure" >&2
        return 17
    fi
    return 0
}
exec() { echo "SERVER:$1"; }
export RUN_MIGRATIONS=true
export DJANGO_SUPERUSER_EMAIL=owner@example.invalid
export DJANGO_SUPERUSER_PASSWORD=dummy-test-only
'''
        script = Path(__file__).resolve().parents[1] / "entrypoint.sh"
        env = {"PATH": os.environ.get("PATH", ""), "RESET_DB_ON_DEPLOY": reset,
               "FAIL_BOOTSTRAP": "yes" if fail_bootstrap else "no"}
        for name in ("SYSTEMROOT", "TEMP", "TMP"):
            if name in os.environ:
                env[name] = os.environ[name]
        return subprocess.run([bash, "--noprofile", "--norc", "-c",
                               harness + script.read_text(encoding="utf-8")],
                              env=env, capture_output=True, text=True, timeout=15)

    def commands(self, result):
        return [line for line in result.stdout.splitlines()
                if line.startswith(("COMMAND:", "SERVER:"))]

    def test_reset_orders_bootstrap_before_existing_owner_and_server(self):
        result = self.run_entrypoint()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.commands(result), [
            "COMMAND:deployment_check", "COMMAND:check", "COMMAND:flush",
            "COMMAND:migrate", "COMMAND:bootstrap_platform", "COMMAND:shell",
            "SERVER:gunicorn",
        ])

    def test_bootstrap_failure_stops_owner_creation_and_server(self):
        result = self.run_entrypoint(fail_bootstrap=True)
        self.assertEqual(result.returncode, 17)
        self.assertIn("simulated bootstrap failure", result.stderr)
        self.assertEqual(self.commands(result)[-1], "COMMAND:bootstrap_platform")
        self.assertNotIn("COMMAND:shell", result.stdout)
        self.assertNotIn("SERVER:", result.stdout)

    def test_disabled_reset_preserves_normal_startup(self):
        result = self.run_entrypoint(reset="false")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.commands(result), [
            "COMMAND:deployment_check", "COMMAND:check", "COMMAND:migrate",
            "COMMAND:shell", "SERVER:gunicorn",
        ])
