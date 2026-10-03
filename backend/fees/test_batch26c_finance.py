"""Real PostgreSQL settlement races, drift rejection and frozen receipts."""
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from academics.models import AcademicSession, Term
from enrollment.models import ClassArm, ClassLevel, StudentProfile
from tenants.models import PlatformEvent, School
from .ledger import account_balance, generate_charges
from .models import FeeCategory, FeePayment, FeeSchedule, PaymentOrder, SchoolPaymentAccount, StudentLedgerEntry, StudentPaymentAllocation
from .payments import settle
from .services.paystack import PaystackService


@override_settings(PAYSTACK_SECRET_KEY="sk_test_batch26c_fixture", PAYSTACK_MODE="test", FRONTEND_URL="http://localhost:3001")
class Batch26CFinanceTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.school = School.objects.create(name="Finance history", slug="finance26c", subdomain="finance26c", subscription_plan="enterprise")
        self.other = School.objects.create(name="Foreign finance", slug="foreign26c", subdomain="foreign26c")
        users = get_user_model().objects
        self.admin = users.create_user(email="admin@finance26c.invalid", password=None, school=self.school, role="school_admin", must_change_password=False)
        self.user = users.create_user(email="student@finance26c.invalid", password=None, school=self.school, role="student", must_change_password=False)
        self.foreign_admin = users.create_user(email="foreign@finance26c.invalid", password=None, school=self.other, role="school_admin", must_change_password=False)
        self.level = ClassLevel.objects.create(school=self.school, name="JSS1")
        self.arm = ClassArm.objects.create(school=self.school, class_level=self.level, name="A")
        self.student = StudentProfile.objects.create(school=self.school, user=self.user, current_class=self.arm, admission_number="FIN26C-1")
        self.session = AcademicSession.objects.create(school=self.school, name="Original session", start_date="2026-09-01", end_date="2027-07-31")
        self.term = Term.objects.create(session=self.session, name="first", start_date="2026-09-01", end_date="2026-12-31")
        self.category = FeeCategory.objects.create(school=self.school, name="Original tuition")
        self.schedule = FeeSchedule.objects.create(school=self.school, term=self.term, class_level=self.level, fee_category=self.category, amount=Decimal("1000.00"))
        SchoolPaymentAccount.objects.create(school=self.school, mode="test", subaccount_code="ACCT_26C", business_name="Finance")
        generate_charges(self.school, self.term, self.admin)

    def client_for(self, user=None, school=None):
        client = APIClient(HTTP_X_SCHOOL_SLUG=(school or self.school).subdomain)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(user or self.admin).access_token))
        return client

    def order(self, amount=100000):
        return PaymentOrder.objects.create(school=self.school, payer=self.user, payer_email=self.user.email, student=self.student,
            kind="fees", mode="test", reference="SCH-26C-" + str(PaymentOrder.objects.count()), status="pending",
            amount_kobo=amount, currency="NGN", subaccount_code="ACCT_26C", allocations=[{"schedule_id": self.schedule.pk, "amount_kobo": amount}])

    def data(self, order):
        return {"reference": order.reference, "status": "success", "amount": order.amount_kobo, "currency": "NGN", "domain": "test", "customer": {"email": order.payer_email}, "id": 26}

    def manual(self, amount="1000.00", key="batch26c-manual-retry", **extra):
        return self.client_for().post("/api/fees/pay/manual/", {"student_id": self.student.pk, "fee_schedule_id": self.schedule.pk,
            "amount_paid": amount, "payment_date": timezone.localdate().isoformat(), "method": "cash", "idempotency_key": key, **extra}, format="json")

    def webhook(self, order):
        body = json.dumps({"event": "charge.success", "data": self.data(order)}).encode()
        signature = hmac.new(b"sk_test_batch26c_fixture", body, hashlib.sha512).hexdigest()
        return APIClient().post("/api/platform/paystack/webhook/", body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=signature)

    def race(self, *jobs):
        barrier = Barrier(len(jobs))
        def run(job):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '15s'")
                    cursor.execute("SET statement_timeout = '30s'")
                barrier.wait(timeout=15)
                return job()
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = [pool.submit(run, job) for job in jobs]
            return [future.result(timeout=60) for future in futures]

    def assert_single_credit(self, order):
        payments = FeePayment.objects.filter(paystack_reference=order.reference)
        self.assertEqual(payments.count(), 1)
        payment = payments.get()
        entry = StudentLedgerEntry.objects.get(fee_payment=payment)
        self.assertEqual(entry.signed_amount, -payment.amount_paid)
        self.assertEqual(StudentLedgerEntry.objects.filter(kind="payment", student=self.student).count(), 1)
        self.assertEqual(StudentPaymentAllocation.objects.filter(credit=entry).count(), 1)
        self.assertEqual(StudentPaymentAllocation.objects.get(credit=entry).amount, payment.amount_paid)
        self.assertEqual(account_balance(self.school, self.student)["outstanding"], Decimal("0.00"))
        self.assertEqual(account_balance(self.school, self.student)["credit"], Decimal("0.00"))
        self.assertEqual(PlatformEvent.objects.filter(action="payment.verified", target=order.reference).count(), 1)

    def test_same_reference_concurrent_settlement_has_one_financial_effect(self):
        order = self.order()
        responses = self.race(lambda: settle(order.reference, self.data(order)), lambda: settle(order.reference, self.data(order)))
        self.assertEqual([r.status for r in responses], ["success", "success"])
        self.assert_single_credit(order)

    def test_signed_webhook_retry_is_idempotent(self):
        order = self.order()
        with patch.object(PaystackService, "verify", return_value=self.data(order)):
            for _ in range(3):
                self.assertEqual(self.webhook(order).status_code, 200)
        self.assert_single_credit(order)

    def test_signed_webhook_and_verify_race_has_one_credit(self):
        order = self.order()
        with patch.object(PaystackService, "verify", return_value=self.data(order)):
            responses = self.race(lambda: self.webhook(order), lambda: self.client_for(self.user).get("/api/fees/pay/verify/", {"reference": order.reference}))
        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assert_single_credit(order)

    def test_manual_and_online_full_payment_cannot_over_credit(self):
        order = self.order()
        manual, online = self.race(lambda: self.manual(), lambda: settle(order.reference, self.data(order)))
        self.assertIn((manual.status_code, online.status), ((201, "review"), (400, "success")))
        self.assertEqual(FeePayment.objects.filter(student=self.student).count(), 1)
        self.assertEqual(StudentLedgerEntry.objects.filter(student=self.student, kind="payment").count(), 1)
        self.assertEqual(StudentPaymentAllocation.objects.count(), 1)
        position = account_balance(self.school, self.student)
        self.assertEqual((position["balance"], position["credit"]), (Decimal("0.00"), Decimal("0.00")))

    def test_distinct_partial_manual_and_online_payments_both_survive(self):
        order = self.order(60000)
        manual, online = self.race(lambda: self.manual("400.00"), lambda: settle(order.reference, self.data(order)))
        self.assertEqual((manual.status_code, online.status), (201, "success"))
        self.assertEqual(FeePayment.objects.count(), 2)
        self.assertEqual(StudentPaymentAllocation.objects.count(), 2)
        self.assertEqual(account_balance(self.school, self.student)["balance"], Decimal("0.00"))

    def test_client_amount_cannot_replace_frozen_checkout_obligation(self):
        with patch.object(PaystackService, "initialize", side_effect=lambda email, amount, ref, callback, **kw: ("https://checkout.paystack.com/test", ref)):
            response = self.client_for(self.user).post("/api/fees/pay/initiate/", {"student_id": self.student.pk,
                "fee_schedule_ids": [self.schedule.pk], "amount": "0.01", "amount_kobo": 1}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(PaymentOrder.objects.get().amount_kobo, 100000)
        self.assertEqual(self.manual("1000.01").status_code, 400)
        self.assertFalse(FeePayment.objects.exists())

    def test_foreign_tenant_reference_cannot_verify_or_read_receipt(self):
        order = self.order()
        with patch.object(PaystackService, "verify") as verify:
            self.assertEqual(self.client_for(self.foreign_admin, self.other).get("/api/fees/pay/verify/", {"reference": order.reference}).status_code, 404)
            self.assertEqual(self.client_for(self.admin, self.other).get("/api/fees/pay/verify/", {"reference": order.reference}).status_code, 403)
            verify.assert_not_called()
        settle(order.reference, self.data(order))
        payment = FeePayment.objects.get(paystack_reference=order.reference)
        self.assertEqual(self.client_for(self.foreign_admin, self.other).get(f"/api/fees/receipts/{payment.pk}/").status_code, 404)
        self.assertFalse(StudentLedgerEntry.objects.filter(school=self.other).exists())

    def test_drift_before_settlement_goes_to_review_without_second_payment(self):
        order = self.order()
        FeePayment.objects.create(school=self.school, student=self.student, fee_schedule=self.schedule,
            amount_paid=Decimal("100.00"), payment_date=timezone.localdate(), method="cash", recorded_by=self.admin)
        self.assertEqual(settle(order.reference, self.data(order)).status, "review")
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertFalse(StudentLedgerEntry.objects.filter(kind="payment").exists())

    def test_successful_order_retry_detects_missing_ledger_entry(self):
        order = self.order()
        settle(order.reference, self.data(order))
        payment = FeePayment.objects.get()
        StudentPaymentAllocation.objects.all().delete()
        StudentLedgerEntry.objects.filter(fee_payment=payment).delete()
        with patch.object(PaystackService, "verify", return_value=self.data(order)):
            response = self.client_for(self.user).get("/api/fees/pay/verify/", {"reference": order.reference})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "review")
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertFalse(StudentLedgerEntry.objects.filter(kind="payment").exists())

    def test_manual_retry_detects_missing_ledger_without_reposting(self):
        response = self.manual()
        self.assertEqual(response.status_code, 201, response.data)
        payment = FeePayment.objects.get()
        StudentPaymentAllocation.objects.all().delete()
        StudentLedgerEntry.objects.filter(fee_payment=payment).delete()
        response = self.manual()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertFalse(StudentLedgerEntry.objects.filter(kind="payment").exists())

    def test_successful_order_retry_detects_missing_allocation(self):
        order = self.order()
        settle(order.reference, self.data(order))
        StudentPaymentAllocation.objects.all().delete()
        self.assertEqual(settle(order.reference, self.data(order)).status, "review")
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertEqual(StudentLedgerEntry.objects.filter(kind="payment").count(), 1)

    def test_pending_reference_with_prior_receipt_cannot_create_another_credit(self):
        order = self.order()
        FeePayment.objects.create(school=self.school, student=self.student, fee_schedule=self.schedule,
            amount_paid=Decimal("1000.00"), payment_date=timezone.localdate(), method="paystack",
            paystack_reference=order.reference, paystack_status="success", recorded_by=self.user)
        self.assertEqual(settle(order.reference, self.data(order)).status, "review")
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertFalse(StudentLedgerEntry.objects.filter(kind="payment").exists())

    def test_receipt_snapshot_survives_mutable_configuration_and_later_balance(self):
        response = self.manual("400.00")
        self.assertEqual(response.status_code, 201, response.data)
        payment = FeePayment.objects.get()
        original = dict(payment.receipt_snapshot)
        self.school.name = "Renamed school"
        self.school.theme_config = {"primary_color": "#FFFFFF"}
        self.school.save(update_fields=["name", "theme_config"])
        FeeSchedule.objects.filter(pk=self.schedule.pk).update(amount=Decimal("9999.00"))
        FeeCategory.objects.filter(pk=self.category.pk).update(name="Renamed fee")
        AcademicSession.objects.filter(pk=self.session.pk).update(name="Renamed session")
        destination = ClassArm.objects.create(school=self.school, class_level=self.level, name="B")
        StudentProfile.objects.filter(pk=self.student.pk).update(current_class=destination)
        self.assertEqual(self.manual("600.00", key="batch26c-later-payment").status_code, 201)
        payment.refresh_from_db()
        self.assertEqual(payment.receipt_snapshot, original)
        self.assertEqual(original["class_name"], "JSS1A")
        self.assertEqual(original["school_name"], "Finance history")
        self.assertEqual(original["amount_paid"], "400.00")
        self.assertEqual(account_balance(self.school, self.student)["balance"], Decimal("0.00"))
