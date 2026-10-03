"""Adversarial welfare, tenant, role and historical-integrity checks on PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from academics.models import AcademicSession
from accounts.models import ParentStudentLink
from tenants.models import Campus, PlatformEvent, School
from .models import (
    AdmissionApplication, ClassArm, ClassLevel, SessionEnrollment, StudentProfile,
    StudentRecordEntry, WelfareCase, WelfareUpdate,
)
from .transfers import transfer_student


class SecurityFixtures:
    @classmethod
    def build(cls):
        cls.school = School.objects.create(name="Security A", slug="security-a", subdomain="security-a", subscription_plan="enterprise")
        cls.foreign = School.objects.create(name="Security B", slug="security-b", subdomain="security-b", subscription_plan="enterprise")
        users = get_user_model().objects

        def actor(role, school=cls.school, label=None):
            return users.create_user(email=f"{label or role}@security26b.invalid", password=None,
                                     role=role, school=school, must_change_password=False)

        cls.actors = {role: actor(role) for role in ("school_admin", "principal", "class_teacher", "teacher", "parent", "student")}
        cls.next_teacher = actor("class_teacher", label="next-class-teacher")
        cls.platform = actor("superadmin", school=None)
        cls.foreign_admin = actor("school_admin", school=cls.foreign, label="foreign-admin")
        cls.level = ClassLevel.objects.create(school=cls.school, name="JSS1")
        cls.foreign_level = ClassLevel.objects.create(school=cls.foreign, name="JSS1")
        cls.arm_a = ClassArm.objects.create(school=cls.school, class_level=cls.level, name="A", class_teacher=cls.actors["class_teacher"])
        cls.arm_b = ClassArm.objects.create(school=cls.school, class_level=cls.level, name="B", class_teacher=cls.next_teacher)
        cls.foreign_arm = ClassArm.objects.create(school=cls.foreign, class_level=cls.foreign_level, name="A")
        cls.student = StudentProfile.objects.create(school=cls.school, user=cls.actors["student"], current_class=cls.arm_a)
        cls.wrong_student = StudentProfile.objects.create(school=cls.school, user=actor("student", label="wrong-class"), current_class=cls.arm_b)
        cls.unplaced = StudentProfile.objects.create(school=cls.school, user=actor("student", label="unplaced"))
        cls.foreign_student = StudentProfile.objects.create(school=cls.foreign, user=actor("student", school=cls.foreign, label="foreign-student"), current_class=cls.foreign_arm)
        ParentStudentLink.objects.create(school=cls.school, parent=cls.actors["parent"], student=cls.student)
        today = timezone.localdate()
        cls.session = AcademicSession.objects.create(school=cls.school, name="Security Session", is_current=True,
                                                     start_date=today - timedelta(days=30), end_date=today + timedelta(days=300))
        cls.student.admission_date = today - timedelta(days=15)
        cls.student.save(update_fields=["admission_date"])
        cls.source = SessionEnrollment.objects.create(school=cls.school, student=cls.student, class_arm=cls.arm_a,
                                                      session=cls.session, enrolled_on=cls.student.admission_date, entry_reason="admission")

        def case(student, category, school=cls.school, reporter=cls.actors["school_admin"]):
            return WelfareCase.objects.create(school=school, student=student, class_arm_snapshot=student.current_class,
                                               category=category, title=category + " confidential case", details="Private " + category,
                                               reported_by=reporter)

        cls.ordinary = case(cls.student, "attendance")
        cls.health = case(cls.student, "health")
        cls.safeguarding = case(cls.student, "safeguarding")
        cls.wrong_case = case(cls.wrong_student, "behaviour")
        cls.foreign_case = case(cls.foreign_student, "health", school=cls.foreign, reporter=cls.foreign_admin)
        WelfareUpdate.objects.create(welfare_case=cls.foreign_case, note="Foreign private follow-up", status_after="open", created_by=cls.foreign_admin)
        cls.foreign_application = AdmissionApplication.objects.create(school=cls.foreign, first_name="Private", last_name="Applicant",
                                                                       guardian_name="Guardian", guardian_phone="0800", applying_class_level=cls.foreign_level)
        cls.record = StudentRecordEntry.objects.create(school=cls.school, student=cls.student, kind="identity", title="Original",
                                                       details="Original identity", effective_date=today, created_by=cls.actors["school_admin"])
        cls.foreign_record = StudentRecordEntry.objects.create(school=cls.foreign, student=cls.foreign_student, kind="identity", title="Foreign",
                                                               details="Foreign private identity", effective_date=today, created_by=cls.foreign_admin)
        cls.campus = Campus.objects.create(school=cls.school, name="Own campus", code="OWN")
        cls.foreign_campus = Campus.objects.create(school=cls.foreign, name="Foreign campus", code="FOREIGN")

    def client_for(self, role="school_admin", tenant=None):
        user = self.actors[role] if isinstance(role, str) else role
        client = APIClient(HTTP_X_SCHOOL_SLUG=(tenant or self.school).subdomain)
        if user.role == "superadmin":
            # Prove denial even after platform authentication/MFA has succeeded.
            client.force_authenticate(user)
        else:
            client.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(user).access_token))
        return client

    def open_case(self, role="school_admin", **overrides):
        payload = {"student": self.student.pk, "category": "attendance", "severity": "low", "title": "Concern", "details": "Private case details"}
        payload.update(overrides)
        return self.client_for(role).post("/api/operations/welfare/", payload, format="json")

    def follow(self, case=None, role="school_admin", **payload):
        return self.client_for(role).post(f"/api/operations/welfare/{(case or self.ordinary).pk}/updates/", payload, format="json")

    def visible(self, role="school_admin"):
        response = self.client_for(role).get("/api/operations/welfare/")
        self.assertEqual(response.status_code, 200, response.content)
        return response.data


class WelfareSecurityTests(SecurityFixtures, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.build()

    def assert_manager(self, role):
        created = self.open_case(role)
        self.assertEqual(created.status_code, 201, created.data)
        row = WelfareCase.objects.get(pk=created.data["id"])
        self.assertEqual(row.school_id, self.school.pk)
        self.assertEqual(row.reported_by_id, self.actors[role].pk)
        self.assertIn(row.pk, [item["id"] for item in self.visible(role)])
        monitored = self.follow(row, role, note="Monitor", status="monitoring")
        self.assertEqual(monitored.status_code, 200, monitored.data)
        resolved = self.follow(row, role, note="Resolved with evidence", status="resolved")
        self.assertEqual(resolved.status_code, 200, resolved.data)
        row.refresh_from_db()
        self.assertEqual(row.status, "resolved")
        self.assertEqual(row.resolved_by_id, self.actors[role].pk)
        self.assertIsNotNone(row.resolved_at)
        self.assertEqual(row.updates.count(), 2)

    def test_school_admin_manages_own_welfare(self):
        self.assert_manager("school_admin")

    def test_principal_manages_own_welfare(self):
        self.assert_manager("principal")

    def test_class_teacher_own_class_all_ordinary_categories(self):
        for category in ("attendance", "behaviour", "academic", "other"):
            with self.subTest(category=category):
                response = self.open_case("class_teacher", category=category)
                self.assertEqual(response.status_code, 201, response.data)
                case = WelfareCase.objects.get(pk=response.data["id"])
                self.assertIn(case.pk, [r["id"] for r in self.visible("class_teacher")])
                update = self.follow(case, "class_teacher", note="Own class follow-up", status="monitoring")
                self.assertEqual(update.status_code, 200, update.data)
                self.assertEqual(case.updates.get().created_by_id, self.actors["class_teacher"].pk)

    def test_wrong_class_teacher_cannot_read_create_follow_or_change_state(self):
        self.assertNotIn(self.wrong_case.pk, [r["id"] for r in self.visible("class_teacher")])
        response = self.open_case("class_teacher", student=self.wrong_student.pk)
        self.assertEqual(response.status_code, 403)
        for state in ("open", "monitoring", "resolved"):
            self.assertEqual(self.follow(self.wrong_case, "class_teacher", note="Unauthorized", status=state).status_code, 404)
        self.wrong_case.refresh_from_db()
        self.assertEqual(self.wrong_case.status, "open")
        self.assertEqual(self.wrong_case.updates.count(), 0)

    def sensitive_denial(self, category, case):
        self.assertEqual(self.open_case("class_teacher", category=category).status_code, 403)
        visible = self.visible("class_teacher")
        self.assertNotIn(case.pk, [r["id"] for r in visible])
        self.assertNotIn(case.details, str(visible))
        self.assertEqual(self.follow(case, "class_teacher", note="Unauthorized", status="resolved").status_code, 404)
        self.assertEqual(case.updates.count(), 0)
        for manager in ("school_admin", "principal"):
            self.assertIn(case.pk, [r["id"] for r in self.visible(manager)])

    def test_health_is_management_only(self):
        self.sensitive_denial("health", self.health)

    def test_safeguarding_is_management_only(self):
        self.sensitive_denial("safeguarding", self.safeguarding)

    def denied_role(self, role):
        before = WelfareCase.objects.count()
        client = self.client_for(role)
        self.assertEqual(client.get("/api/operations/welfare/").status_code, 403)
        self.assertEqual(self.open_case(role).status_code, 403)
        self.assertEqual(self.follow(role=role, note="Unauthorized", status="resolved").status_code, 403)
        self.assertEqual(WelfareCase.objects.count(), before)
        self.assertEqual(self.ordinary.updates.count(), 0)

    def test_ordinary_teacher_does_not_inherit_homeroom_role(self):
        self.arm_a.class_teacher = self.actors["teacher"]
        self.arm_a.save(update_fields=["class_teacher"])
        self.denied_role("teacher")

    def test_linked_parent_cannot_access_internal_welfare(self):
        self.denied_role("parent")

    def test_student_cannot_access_own_internal_welfare(self):
        self.denied_role("student")

    def test_platform_owner_has_no_implicit_welfare_authority(self):
        self.denied_role(self.platform)

    def test_anonymous_welfare_requests_denied(self):
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.subdomain)
        self.assertEqual(client.get("/api/operations/welfare/").status_code, 401)
        self.assertEqual(client.post("/api/operations/welfare/", {}, format="json").status_code, 401)
        self.assertEqual(client.post(f"/api/operations/welfare/{self.ordinary.pk}/updates/", {"note": "Anonymous"}, format="json").status_code, 401)

    def test_cross_tenant_student_ids_fail_closed(self):
        for role in ("school_admin", "principal", "class_teacher"):
            self.assertEqual(self.open_case(role, student=self.foreign_student.pk).status_code, 400)
        self.assertEqual(WelfareCase.objects.filter(school=self.school, student=self.foreign_student).count(), 0)

    def test_cross_tenant_case_ids_and_followups_are_hidden(self):
        for role in ("school_admin", "principal", "class_teacher"):
            visible = self.visible(role)
            self.assertNotIn(self.foreign_case.pk, [r["id"] for r in visible])
            self.assertNotIn("Foreign private", str(visible))
            self.assertEqual(self.follow(self.foreign_case, role, note="Cross tenant", status="resolved").status_code, 404)
        self.foreign_case.refresh_from_db()
        self.assertEqual(self.foreign_case.status, "open")
        self.assertEqual(self.foreign_case.updates.get().note, "Foreign private follow-up")

    def test_forged_tenant_header_does_not_grant_privileged_access(self):
        for role in ("school_admin", "principal", "class_teacher"):
            client = self.client_for(role, self.foreign)
            for url in ("/api/operations/welfare/", "/api/operations/admissions/", f"/api/operations/student-records/{self.foreign_student.pk}/"):
                self.assertEqual(client.get(url).status_code, 403)
            self.assertEqual(client.post(f"/api/operations/welfare/{self.foreign_case.pk}/updates/", {"note": "Forged header"}, format="json").status_code, 403)
            self.assertEqual(client.post(f"/api/operations/admissions/{self.foreign_application.pk}/documents/", {}, format="json").status_code, 403)
        self.assertEqual(self.client_for("school_admin", self.foreign).get("/api/campuses/").status_code, 403)

    def test_spoofed_payload_cannot_replace_tenant_author_or_original_case(self):
        response = self.open_case(school=self.foreign.pk, reported_by=self.foreign_admin.pk, class_arm_snapshot=self.foreign_arm.pk)
        self.assertEqual(response.status_code, 201, response.data)
        case = WelfareCase.objects.get(pk=response.data["id"])
        self.assertEqual(case.school_id, self.school.pk)
        self.assertEqual(case.reported_by_id, self.actors["school_admin"].pk)
        self.assertEqual(case.class_arm_snapshot_id, self.arm_a.pk)
        response = self.follow(case, note="Attributed note", created_by=self.foreign_admin.pk, welfare_case=self.foreign_case.pk,
                               school=self.foreign.pk, updates=[{"id": 1, "note": "Overwrite"}])
        self.assertEqual(response.status_code, 200, response.data)
        update = case.updates.get()
        self.assertEqual(update.created_by_id, self.actors["school_admin"].pk)
        self.assertEqual(update.note, "Attributed note")

    def test_missing_or_unknown_tenant_selection_is_denied(self):
        token = str(RefreshToken.for_user(self.actors["school_admin"]).access_token)
        # Missing selection reaches the view with tenant=None; unknown selection
        # is rejected by middleware. Both must deny access before any disclosure.
        for client, expected in ((APIClient(), 403), (APIClient(HTTP_X_SCHOOL_SLUG="unknown-school"), 404)):
            client.credentials(HTTP_AUTHORIZATION="Bearer " + token)
            self.assertEqual(client.get("/api/operations/welfare/").status_code, expected)

    def test_invalid_status_and_blank_notes_leave_state_and_history_intact(self):
        for payload in ({"note": "   ", "status": "resolved"}, {"note": "Invalid state", "status": "deleted"}):
            self.assertEqual(self.follow(**payload).status_code, 400)
        self.ordinary.refresh_from_db()
        self.assertEqual(self.ordinary.status, "open")
        self.assertIsNone(self.ordinary.resolved_by_id)
        self.assertEqual(self.ordinary.updates.count(), 0)

    def test_followup_history_is_append_only_and_resolution_metadata_is_coherent(self):
        first = self.follow(note="Original note one", status="monitoring")
        self.assertEqual(first.status_code, 200, first.data)
        second = self.follow(role="principal", note="Original note two", status="resolved")
        self.assertEqual(second.status_code, 200, second.data)
        original = list(self.ordinary.updates.values("id", "note", "status_after", "created_by_id", "created_at"))
        self.assertEqual(len(original), 2)
        client = self.client_for()
        for method in (client.patch, client.delete):
            response = method(f"/api/operations/welfare/{self.ordinary.pk}/updates/", {"id": original[0]["id"], "note": "Overwrite"}, format="json")
            self.assertEqual(response.status_code, 405)
        self.assertEqual(client.patch(f"/api/operations/welfare/{self.ordinary.pk}/updates/{original[0]['id']}/", {"note": "Overwrite"}, format="json").status_code, 404)
        self.assertEqual(self.follow(note="Reopen with new evidence", status="open").status_code, 200)
        self.assertEqual(list(self.ordinary.updates.order_by("created_at", "id").values("id", "note", "status_after", "created_by_id", "created_at"))[:2], original)
        self.ordinary.refresh_from_db()
        self.assertEqual(self.ordinary.updates.count(), 3)
        self.assertEqual(self.ordinary.details, "Private attendance")
        self.assertIsNone(self.ordinary.resolved_at)
        self.assertIsNone(self.ordinary.resolved_by_id)

    def test_nullable_class_and_resolution_joins_are_writable_on_postgresql(self):
        self.assertEqual(connection.vendor, "postgresql", "Batch 26B must run on PostgreSQL")
        created = self.open_case(student=self.unplaced.pk)
        self.assertEqual(created.status_code, 201, created.data)
        case = WelfareCase.objects.get(pk=created.data["id"])
        self.assertIsNone(case.class_arm_snapshot_id)
        self.assertEqual(self.follow(case, note="No class assigned", status="monitoring").status_code, 200)
        self.assertEqual(self.follow(case, note="Resolved", status="resolved").status_code, 200)

    def test_transfer_preserves_case_class_and_session_history_without_inherited_access(self):
        old_id, old_details = self.ordinary.class_arm_snapshot_id, self.ordinary.details
        transfer_student(school=self.school, student=self.student, destination_class=self.arm_b,
                         effective_date=timezone.localdate(), actor=self.actors["school_admin"], reason="Real class transfer")
        self.ordinary.refresh_from_db()
        self.source.refresh_from_db()
        self.assertEqual(self.ordinary.class_arm_snapshot_id, old_id)
        self.assertEqual(self.ordinary.details, old_details)
        self.assertEqual(self.source.class_arm_id, self.arm_a.pk)
        self.assertEqual(self.source.session_id, self.session.pk)
        self.assertEqual(self.source.status, "transferred")
        self.assertEqual(SessionEnrollment.objects.filter(student=self.student, session=self.session).count(), 2)
        future = self.open_case(category="academic")
        self.assertEqual(future.status_code, 201, future.data)
        self.assertEqual(future.data["class_arm"], self.arm_b.pk)
        for teacher in (self.actors["class_teacher"], self.next_teacher):
            ids = [r["id"] for r in self.visible(teacher)]
            self.assertNotIn(self.ordinary.pk, ids)
            self.assertNotIn(self.health.pk, ids)
            self.assertNotIn(self.safeguarding.pk, ids)
            self.assertEqual(self.follow(self.ordinary, teacher, note="Old history").status_code, 404)
        self.assertNotIn(future.data["id"], [r["id"] for r in self.visible("class_teacher")])
        self.assertEqual(self.client_for("class_teacher").post(
            f"/api/operations/welfare/{future.data['id']}/updates/",
            {"note": "Former teacher cannot update future history"}, format="json",
        ).status_code, 404)
        self.assertIn(future.data["id"], [r["id"] for r in self.visible(self.next_teacher)])
        original = next(r for r in self.visible() if r["id"] == self.ordinary.pk)
        self.assertEqual(original["class_arm"], self.arm_a.pk)
        self.assertEqual(original["class_name"], "JSS1A")

    def test_current_delegation_can_be_revoked_without_changing_reporter(self):
        self.arm_a.class_teacher = self.next_teacher
        self.arm_a.save(update_fields=["class_teacher"])
        self.assertNotIn(self.ordinary.pk, [r["id"] for r in self.visible("class_teacher")])
        self.assertEqual(self.follow(role="class_teacher", note="Revoked").status_code, 404)
        self.assertIn(self.ordinary.pk, [r["id"] for r in self.visible(self.next_teacher)])
        self.assertNotIn(self.health.pk, [r["id"] for r in self.visible(self.next_teacher)])
        self.assertEqual(self.ordinary.reported_by_id, self.actors["school_admin"].pk)

    def test_inconsistent_tenant_relations_fail_closed(self):
        bad_student = WelfareCase.objects.create(school=self.school, student=self.foreign_student, category="attendance",
                                                 title="Corrupt student link", details="Foreign data", reported_by=self.actors["school_admin"])
        bad_class = WelfareCase.objects.create(school=self.school, student=self.student, class_arm_snapshot=self.foreign_arm,
                                               category="attendance", title="Corrupt class link", details="Foreign class", reported_by=self.actors["school_admin"])
        for role in ("school_admin", "principal", "class_teacher"):
            ids = [r["id"] for r in self.visible(role)]
            for case in (bad_student, bad_class):
                self.assertNotIn(case.pk, ids)
                self.assertEqual(self.follow(case, role, note="Corrupt relation").status_code, 404)

    def test_mismatched_student_account_school_is_not_usable(self):
        malformed = StudentProfile.objects.create(school=self.school, user=self.foreign_admin, current_class=self.arm_a)
        self.assertEqual(self.open_case(student=malformed.pk).status_code, 400)
        case = WelfareCase.objects.create(
            school=self.school, student=malformed, class_arm_snapshot=self.arm_a,
            category="attendance", title="Corrupt account link", details="Foreign account",
            reported_by=self.actors["school_admin"],
        )
        for role in ("school_admin", "principal", "class_teacher"):
            self.assertNotIn(case.pk, [r["id"] for r in self.visible(role)])
            self.assertEqual(self.follow(case, role, note="Foreign account").status_code, 404)

    def test_admission_cross_tenant_read_and_foreign_references(self):
        for role in ("school_admin", "principal"):
            client = self.client_for(role)
            listed = client.get("/api/operations/admissions/")
            self.assertEqual(listed.status_code, 200)
            self.assertNotIn(self.foreign_application.pk, [r["id"] for r in listed.data])
            payload = {"first_name": "Own", "last_name": "Applicant", "guardian_name": "Guardian", "guardian_phone": "0800", "applying_class_level": self.foreign_level.pk}
            self.assertEqual(client.post("/api/operations/admissions/", payload, format="json").status_code, 400)
            payload.update(applying_class_level=self.level.pk, preferred_campus=self.foreign_campus.pk)
            self.assertEqual(client.post("/api/operations/admissions/", payload, format="json").status_code, 400)

    def test_student_record_cross_tenant_writes_and_supersession_denied(self):
        payload = {"kind": "identity", "title": "Correction", "details": "Correction evidence", "effective_date": timezone.localdate().isoformat()}
        for role in ("school_admin", "principal"):
            client = self.client_for(role)
            self.assertEqual(client.post(f"/api/operations/student-records/{self.foreign_student.pk}/", payload, format="json").status_code, 404)
            response = client.post(f"/api/operations/student-records/{self.student.pk}/", {**payload, "supersedes": self.foreign_record.pk}, format="json")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(StudentRecordEntry.objects.filter(student=self.student).count(), 1)
        self.foreign_record.refresh_from_db()
        self.assertEqual(self.foreign_record.details, "Foreign private identity")

    def test_campus_cross_tenant_read_patch_and_delete_fail_closed(self):
        client = self.client_for()
        listed = client.get("/api/campuses/")
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn(self.foreign_campus.pk, [r["id"] for r in listed.data])
        self.assertEqual(client.patch(f"/api/campuses/{self.foreign_campus.pk}/", {"name": "Overwrite"}, format="json").status_code, 404)
        self.assertEqual(client.delete(f"/api/campuses/{self.foreign_campus.pk}/").status_code, 404)
        self.foreign_campus.refresh_from_db()
        self.assertEqual(self.foreign_campus.name, "Foreign campus")
        own = client.patch(f"/api/campuses/{self.campus.pk}/", {"school": self.foreign.pk, "name": "Own correction"}, format="json")
        self.assertEqual(own.status_code, 200, own.data)
        self.campus.refresh_from_db()
        self.assertEqual(self.campus.school_id, self.school.pk)

    def test_related_institutional_endpoints_keep_explicit_role_boundaries(self):
        for role in ("class_teacher", "teacher", "parent", "student", self.platform):
            client = self.client_for(role)
            for url in ("/api/operations/admissions/", f"/api/operations/student-records/{self.student.pk}/", "/api/campuses/"):
                self.assertEqual(client.get(url).status_code, 403)
                self.assertEqual(client.post(url, {}, format="json").status_code, 403)
            self.assertEqual(client.post(f"/api/operations/admissions/{self.foreign_application.pk}/documents/", {}, format="json").status_code, 403)
        self.assertEqual(self.client_for("principal").get("/api/campuses/").status_code, 403)
        self.assertEqual(self.client_for("principal").post("/api/campuses/", {}, format="json").status_code, 403)


class WelfareConcurrencyTests(SecurityFixtures, TransactionTestCase):
    def setUp(self):
        self.assertEqual(connection.vendor, "postgresql", "Real PostgreSQL locking required")
        self.build()

    def concurrent(self, payloads):
        barrier = Barrier(len(payloads))

        def run(item):
            role, payload = item
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '15s'")
                    cursor.execute("SET statement_timeout = '30s'")
                barrier.wait(timeout=15)
                response = self.follow(role=role, **payload)
                self.assertEqual(response.status_code, 200, response.content)
                return response.data
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
            futures = [pool.submit(run, item) for item in payloads]
            return [future.result(timeout=60) for future in futures]

    def assert_coherent_audits(self, count):
        updates = list(self.ordinary.updates.order_by("created_at", "id"))
        events = list(PlatformEvent.objects.filter(action="welfare.case_updated", target=f"welfare:{self.ordinary.pk}").order_by("id"))
        self.assertEqual(len(updates), count)
        self.assertEqual(len(events), count)
        previous_status = "open"
        for update, event in zip(updates, events):
            self.assertEqual(event.actor_id, update.created_by_id)
            self.assertEqual(event.details["school_id"], self.school.pk)
            self.assertEqual(event.details["update_id"], update.pk)
            self.assertEqual(event.details["status"], update.status_after)
            self.assertEqual(event.details["status_before"], previous_status)
            previous_status = update.status_after
            self.assertNotIn(update.note, str(event.details))
        self.ordinary.refresh_from_db()
        self.assertEqual(self.ordinary.status, updates[-1].status_after)

    def test_two_concurrent_notes_are_retained_and_attributable(self):
        self.concurrent([("school_admin", {"note": "Admin follow-up"}), ("principal", {"note": "Principal follow-up"})])
        self.assertEqual(set(self.ordinary.updates.values_list("note", flat=True)), {"Admin follow-up", "Principal follow-up"})
        self.assert_coherent_audits(2)

    def test_concurrent_note_and_resolution_preserve_state_and_history(self):
        self.concurrent([("school_admin", {"note": "State-neutral note"}), ("principal", {"note": "Resolved after review", "status": "resolved"})])
        self.assert_coherent_audits(2)
        self.ordinary.refresh_from_db()
        self.assertEqual(self.ordinary.status, "resolved")
        self.assertEqual(self.ordinary.resolved_by_id, self.actors["principal"].pk)
        self.assertIsNotNone(self.ordinary.resolved_at)

    def test_duplicate_resolution_requests_append_history_without_replacing_actor(self):
        self.concurrent([("school_admin", {"note": "Resolution retry", "status": "resolved"}), ("principal", {"note": "Resolution retry", "status": "resolved"})])
        self.assert_coherent_audits(2)
        first = self.ordinary.updates.order_by("created_at", "id").first()
        self.ordinary.refresh_from_db()
        self.assertEqual(self.ordinary.resolved_by_id, first.created_by_id)
