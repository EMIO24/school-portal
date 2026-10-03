"""Campus references survive retirement; placements and primary races fail safe."""
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from academics.models import AcademicSession
from enrollment.class_structure import ensure_default_arm
from enrollment.models import AdmissionApplication, ClassArm, ClassLevel, SessionEnrollment, StaffProfile, StudentProfile, StudentRecordEntry
from .models import Campus, School


class Batch26CCampusTests(TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql")
        self.school = School.objects.create(name="Campus history", slug="campus26c", subdomain="campus26c", subscription_plan="enterprise")
        self.other = School.objects.create(name="Foreign campus", slug="campus26foreign", subdomain="campus26foreign", subscription_plan="enterprise")
        users = get_user_model().objects
        self.admin = users.create_user(email="admin@campus26c.invalid", password=None, school=self.school, role="school_admin", must_change_password=False)
        self.teacher = users.create_user(email="teacher@campus26c.invalid", password=None, school=self.school, role="teacher", must_change_password=False)
        self.user = users.create_user(email="student@campus26c.invalid", password=None, school=self.school, role="student", must_change_password=False)
        self.campus = Campus.objects.create(school=self.school, name="Original campus", code="ORIGINAL", is_primary=True)
        self.second = Campus.objects.create(school=self.school, name="Second campus", code="SECOND")
        self.foreign = Campus.objects.create(school=self.other, name="Foreign campus", code="FOREIGN")
        self.level = ClassLevel.objects.create(school=self.school, name="JSS1")
        self.arm = ClassArm.objects.create(school=self.school, class_level=self.level, name="A", campus=self.campus)
        self.staff = StaffProfile.objects.create(school=self.school, user=self.teacher, campus=self.campus)
        self.student = StudentProfile.objects.create(school=self.school, user=self.user, current_class=self.arm, admission_number="CAMP26-1")
        self.session = AcademicSession.objects.create(school=self.school, name="Campus session", is_current=True, start_date=date(2026, 9, 1), end_date=date(2027, 7, 31))
        self.enrollment = SessionEnrollment.objects.create(school=self.school, student=self.student, session=self.session, class_arm=self.arm, enrolled_on=date(2026, 9, 1))
        self.record = StudentRecordEntry.objects.create(school=self.school, student=self.student, kind="identity", title="Historical identity", details="Preserve", effective_date="2026-09-01", created_by=self.admin)
        self.application = AdmissionApplication.objects.create(school=self.school, first_name="Applicant", last_name="History", guardian_name="Guardian", guardian_phone="0800", applying_class_level=self.level, preferred_campus=self.campus)

    def client_for(self, user=None):
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.subdomain)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(user or self.admin).access_token))
        return client

    def retire(self):
        response = self.client_for().patch(f"/api/campuses/{self.campus.pk}/", {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200, response.data)

    def test_referenced_class_staff_campus_cannot_be_deleted(self):
        self.assertEqual(self.client_for().delete(f"/api/campuses/{self.campus.pk}/").status_code, 409)
        self.assertTrue(Campus.objects.filter(pk=self.campus.pk).exists())

    def test_admission_only_reference_returns_conflict_and_preserves_history(self):
        self.application.preferred_campus = self.second
        self.application.save(update_fields=["preferred_campus"])
        self.assertEqual(self.client_for().delete(f"/api/campuses/{self.second.pk}/").status_code, 409)
        self.application.refresh_from_db()
        self.assertEqual(self.application.preferred_campus_id, self.second.pk)

    def test_deactivation_preserves_all_historical_references_and_unrelated_edits(self):
        self.retire()
        for row in (self.arm, self.staff, self.application, self.enrollment, self.record):
            row.refresh_from_db()
        self.assertEqual(self.arm.campus_id, self.campus.pk)
        self.assertEqual(self.staff.campus_id, self.campus.pk)
        self.assertEqual(self.application.preferred_campus_id, self.campus.pk)
        self.assertEqual(self.enrollment.class_arm.campus_id, self.campus.pk)
        self.assertEqual(self.record.details, "Preserve")
        self.assertEqual(self.client_for().patch(f"/api/class-arms/{self.arm.pk}/", {"name": "RENAMED"}, format="json").status_code, 200)
        self.assertEqual(self.client_for().patch(f"/api/staff/{self.staff.pk}/", {"qualification": "bsc"}, format="json").status_code, 200)

    def test_inactive_campus_cannot_receive_new_class_or_staff(self):
        self.retire()
        client = self.client_for()
        self.assertEqual(client.post("/api/class-arms/", {"class_level": self.level.pk, "name": "NEW", "campus": self.campus.pk}, format="json").status_code, 400)
        self.staff.campus = self.second
        self.staff.save(update_fields=["campus"])
        self.assertEqual(client.patch(f"/api/staff/{self.staff.pk}/", {"campus": self.campus.pk}, format="json").status_code, 400)

    def test_inactive_admission_preference_and_implicit_destination_denied(self):
        self.retire()
        client = self.client_for()
        self.assertEqual(client.post("/api/operations/admissions/", {"first_name": "New", "last_name": "Applicant", "guardian_name": "G", "guardian_phone": "0800", "applying_class_level": self.level.pk, "preferred_campus": self.campus.pk}, format="json").status_code, 400)
        response = client.post(f"/api/operations/admissions/{self.application.pk}/decision/", {"decision": "admit", "class_arm": self.arm.pk}, format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.application.refresh_from_db()
        self.assertNotEqual(self.application.status, "admitted")

    def test_cross_tenant_class_staff_and_admission_assignment_denied(self):
        client = self.client_for()
        self.assertEqual(client.post("/api/class-arms/", {"class_level": self.level.pk, "name": "FOREIGN", "campus": self.foreign.pk}, format="json").status_code, 400)
        self.assertEqual(client.patch(f"/api/staff/{self.staff.pk}/", {"campus": self.foreign.pk}, format="json").status_code, 400)
        self.assertEqual(client.post("/api/operations/admissions/", {"first_name": "New", "last_name": "Applicant", "guardian_name": "G", "guardian_phone": "0800", "applying_class_level": self.level.pk, "preferred_campus": self.foreign.pk}, format="json").status_code, 400)
        self.assertEqual(client.patch(f"/api/campuses/{self.foreign.pk}/", {"is_primary": True}, format="json").status_code, 404)

    def test_enterprise_creation_and_ordinary_teacher_denial(self):
        self.school.subscription_plan = "premium"
        self.school.save(update_fields=["subscription_plan"])
        self.assertEqual(self.client_for().post("/api/campuses/", {"name": "Blocked", "code": "BLOCK"}, format="json").status_code, 403)
        self.assertEqual(self.client_for(self.teacher).patch(f"/api/campuses/{self.campus.pk}/", {"is_active": False}, format="json").status_code, 403)

    def test_nullable_legacy_and_no_arm_campus_defaults_do_not_collide(self):
        legacy = ClassArm.objects.create(school=self.school, class_level=self.level, name="LEGACY", campus=None)
        self.assertIsNone(legacy.campus_id)
        self.school.uses_class_arms = False
        self.school.save(update_fields=["uses_class_arms"])
        first = ensure_default_arm(school=self.school, class_level=self.level, campus=self.campus)
        second = ensure_default_arm(school=self.school, class_level=self.level, campus=self.second)
        nullable = ensure_default_arm(school=self.school, class_level=self.level)
        self.assertEqual(len({first.pk, second.pk, nullable.pk}), 3)
        self.assertEqual(ensure_default_arm(school=self.school, class_level=self.level, campus=self.campus).pk, first.pk)
        self.assertIsNone(nullable.campus_id)

    def test_concurrent_primary_changes_both_complete_with_one_primary(self):
        barrier = Barrier(2)
        def promote(pk):
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '15s'")
                    cursor.execute("SET statement_timeout = '30s'")
                barrier.wait(timeout=15)
                response = self.client_for().patch(f"/api/campuses/{pk}/", {"is_primary": True}, format="json")
                self.assertEqual(response.status_code, 200, response.content)
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(promote, pk) for pk in (self.campus.pk, self.second.pk)]
            for future in futures:
                future.result(timeout=60)
        self.assertEqual(Campus.objects.filter(school=self.school, is_primary=True).count(), 1)
        self.assertFalse(Campus.objects.get(pk=self.foreign.pk).is_primary)
