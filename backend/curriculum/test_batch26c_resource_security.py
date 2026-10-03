"""Adversarial author/reviewer boundaries and immutable institutional resources."""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from academics.models import AcademicSession, Term
from accounts.models import ParentStudentLink
from enrollment.models import ClassArm, ClassLevel, SessionEnrollment, StaffProfile, StudentProfile, Subject, SubjectAssignment
from enrollment.transfers import transfer_student
from tenants.models import School
from .models import AcademicResource


class Batch26CResourceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="Resource history", slug="resource26c", subdomain="resource26c", subscription_plan="premium")
        cls.other = School.objects.create(name="Foreign resource", slug="resourceforeign26c", subdomain="resourceforeign26c", subscription_plan="premium")
        users = get_user_model().objects
        cls.actors = {role: users.create_user(email=f"{role}@resource26c.invalid", password=None, school=cls.school,
            role=role, must_change_password=False) for role in ("school_admin", "principal", "teacher", "parent", "student")}
        cls.unassigned = users.create_user(email="unassigned@resource26c.invalid", password=None, school=cls.school, role="teacher", must_change_password=False)
        cls.level = ClassLevel.objects.create(school=cls.school, name="JSS1")
        cls.next_level = ClassLevel.objects.create(school=cls.school, name="JSS2")
        cls.foreign_level = ClassLevel.objects.create(school=cls.other, name="JSS1")
        cls.arm = ClassArm.objects.create(school=cls.school, class_level=cls.level, name="A")
        cls.next_arm = ClassArm.objects.create(school=cls.school, class_level=cls.next_level, name="B")
        cls.subject = Subject.objects.create(school=cls.school, name="Mathematics", code="MATH")
        cls.subject.class_levels.add(cls.level, cls.next_level)
        cls.unrelated_subject = Subject.objects.create(school=cls.school, name="Unrelated subject", code="OTHER")
        cls.unrelated_subject.class_levels.add(cls.next_level)
        cls.foreign_subject = Subject.objects.create(school=cls.other, name="Foreign maths", code="MATH")
        today = timezone.localdate()
        cls.session = AcademicSession.objects.create(school=cls.school, name="Resource session 1", is_current=True, start_date=today-timedelta(days=30), end_date=today+timedelta(days=300))
        cls.term = Term.objects.create(session=cls.session, name="first", start_date=today-timedelta(days=30), end_date=today+timedelta(days=60), is_current=True)
        cls.staff = StaffProfile.objects.create(school=cls.school, user=cls.actors["teacher"])
        cls.assignment = SubjectAssignment.objects.create(school=cls.school, teacher=cls.staff, class_arm=cls.arm, subject=cls.subject, session=cls.session, term=cls.term)
        cls.student = StudentProfile.objects.create(school=cls.school, user=cls.actors["student"], current_class=cls.arm, admission_date=today-timedelta(days=15))
        cls.student.admission_date = today - timedelta(days=15)
        cls.student.save(update_fields=["admission_date"])
        cls.enrollment = SessionEnrollment.objects.create(school=cls.school, student=cls.student, session=cls.session, class_arm=cls.arm, enrolled_on=cls.student.admission_date)
        ParentStudentLink.objects.create(school=cls.school, parent=cls.actors["parent"], student=cls.student)
        cls.approved = AcademicResource.objects.create(school=cls.school, class_level=cls.level, subject=cls.subject, title="Original approved note",
            kind="note", content="Original content", external_url="https://example.invalid/original", status="approved",
            created_by=cls.actors["teacher"], reviewed_by=cls.actors["principal"], approved_by=cls.actors["principal"], approved_at=timezone.now())
        cls.foreign_resource = AcademicResource.objects.create(school=cls.other, class_level=cls.foreign_level, subject=cls.foreign_subject,
            title="Foreign private resource", kind="note", content="Foreign content", status="approved")

    def client_for(self, role="teacher", school=None):
        user = self.actors[role] if isinstance(role, str) else role
        client = APIClient(HTTP_X_SCHOOL_SLUG=(school or self.school).subdomain)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(user).access_token))
        return client

    def create(self, role="teacher", **extra):
        return self.client_for(role).post("/api/curriculum/resources/", {"class_level": self.level.pk, "subject": self.subject.pk,
            "title": "New teacher note", "kind": "note", "content": "Evidence", **extra}, format="json")

    def transition(self, pk, action, role="teacher", **extra):
        return self.client_for(role).post(f"/api/curriculum/resources/{pk}/transition/", {"action": action, **extra}, format="json")

    def test_assigned_teacher_authors_only_assigned_level_subject(self):
        created = self.create()
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["resource"]["created_by"], self.actors["teacher"].pk)
        self.assertEqual(self.create(class_level=self.next_level.pk).status_code, 403)
        self.assertEqual(self.create(subject=self.unrelated_subject.pk).status_code, 403)
        self.assertEqual(self.create(self.unassigned).status_code, 403)
        self.assertEqual(self.transition(created.data["resource"]["id"], "review").status_code, 409)

    def test_revoked_assignment_cannot_submit_owned_draft(self):
        created = self.create()
        self.assertEqual(created.status_code, 201, created.data)
        self.assignment.delete()
        response = self.transition(created.data["resource"]["id"], "submit")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AcademicResource.objects.get(pk=created.data["resource"]["id"]).status, "draft")

    def test_principal_reviews_but_cannot_author_or_revise_as_author(self):
        self.assertEqual(self.create("principal").status_code, 403)
        self.assertEqual(self.client_for("principal").post(f"/api/curriculum/resources/{self.approved.pk}/revise/", {}, format="json").status_code, 403)
        created = self.create()
        pk = created.data["resource"]["id"]
        for role, action in (("teacher", "submit"), ("principal", "review"), ("principal", "approve")):
            self.assertEqual(self.transition(pk, action, role).status_code, 200)
        row = AcademicResource.objects.get(pk=pk)
        self.assertEqual(row.created_by_id, self.actors["teacher"].pk)
        self.assertEqual(row.approved_by_id, self.actors["principal"].pk)

    def test_student_visibility_excludes_unapproved_unrelated_and_foreign_resources(self):
        for status in ("draft", "submitted", "reviewed"):
            AcademicResource.objects.create(school=self.school, class_level=self.level, subject=self.subject, title=status+" private note", kind="note", status=status)
        AcademicResource.objects.create(school=self.school, class_level=self.next_level, subject=self.subject, title="Other level", kind="note", status="approved")
        # A legacy inconsistent row must not bypass subject/class relevance.
        AcademicResource.objects.create(school=self.school, class_level=self.level, subject=self.unrelated_subject, title="Unrelated subject", kind="note", status="approved")
        response = self.client_for("student").get("/api/curriculum/student-resources/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r["id"] for r in response.data["resources"]], [self.approved.pk])

    def test_parent_has_no_internal_or_student_resource_authority(self):
        for url in ("/api/curriculum/resources/", "/api/curriculum/student-resources/"):
            self.assertEqual(self.client_for("parent").get(url).status_code, 403)
        self.assertEqual(self.create("parent").status_code, 403)

    def test_foreign_resource_ids_and_forged_tenant_selection_fail_closed(self):
        for role in ("teacher", "principal", "school_admin"):
            response = self.client_for(role).get("/api/curriculum/resources/")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(self.foreign_resource.pk, [r["id"] for r in response.data["resources"]])
            self.assertEqual(self.transition(self.foreign_resource.pk, "approve", role).status_code, 404)
            self.assertEqual(self.client_for(role).post(f"/api/curriculum/resources/{self.foreign_resource.pk}/revise/", {}, format="json").status_code, 409)
            self.assertEqual(self.client_for(role, self.other).get("/api/curriculum/resources/").status_code, 403)
        self.assertEqual(self.create(class_level=self.foreign_level.pk).status_code, 400)
        self.assertEqual(self.create(subject=self.foreign_subject.pk).status_code, 400)
        self.assertEqual(self.client_for("student", self.other).get("/api/curriculum/student-resources/").status_code, 403)

    def test_approved_content_and_approval_metadata_survive_mutation_attempts_and_revision(self):
        original = AcademicResource.objects.filter(pk=self.approved.pk).values().get()
        payload = {"title": "Overwrite", "content": "Overwrite", "external_url": "https://example.invalid/overwrite", "class_level": self.next_level.pk,
            "subject": self.unrelated_subject.pk, "approved_by": self.actors["teacher"].pk}
        self.assertEqual(self.transition(self.approved.pk, "submit", **payload).status_code, 409)
        for method in (self.client_for().patch, self.client_for().delete):
            self.assertEqual(method(f"/api/curriculum/resources/{self.approved.pk}/", payload, format="json").status_code, 404)
        revised = self.client_for().post(f"/api/curriculum/resources/{self.approved.pk}/revise/", payload, format="json")
        self.assertEqual(revised.status_code, 201, revised.data)
        new = AcademicResource.objects.get(pk=revised.data["resource"]["id"])
        self.assertEqual((new.revision, new.status, new.supersedes_id), (2, "draft", self.approved.pk))
        self.assertEqual((new.title, new.content, new.external_url, new.class_level_id, new.subject_id),
            (self.approved.title, self.approved.content, self.approved.external_url, self.level.pk, self.subject.pk))
        self.assertIsNone(new.approved_by_id)
        self.assertIsNone(new.approved_at)
        self.assertEqual(AcademicResource.objects.filter(pk=self.approved.pk).values().get(), original)
        self.assertEqual(self.client_for().post(f"/api/curriculum/resources/{self.approved.pk}/revise/", {}, format="json").status_code, 409)
        self.assertIn(self.approved.pk, [r["id"] for r in self.client_for("school_admin").get("/api/curriculum/resources/").data["resources"]])

    def test_unassigned_teacher_cannot_revise_approved_work(self):
        self.assertEqual(self.client_for(self.unassigned).post(f"/api/curriculum/resources/{self.approved.pk}/revise/", {}, format="json").status_code, 403)

    def test_transfer_and_new_session_preserve_historical_resource_and_membership(self):
        old = AcademicResource.objects.filter(pk=self.approved.pk).values().get()
        transfer_student(school=self.school, student=self.student, destination_class=self.next_arm, effective_date=timezone.localdate(), actor=self.actors["school_admin"], reason="Resource transfer")
        next_session = AcademicSession.objects.create(school=self.school, name="Resource session 2", start_date=date(2027, 9, 1), end_date=date(2028, 7, 31), is_current=True)
        SessionEnrollment.objects.create(school=self.school, student=self.student, class_arm=self.next_arm, session=next_session, enrolled_on=date(2027, 9, 1))
        current = AcademicResource.objects.create(school=self.school, class_level=self.next_level, subject=self.subject, title="Next level approved", kind="note", content="Current institutional content", status="approved")
        response = self.client_for("student").get("/api/curriculum/student-resources/", {"class_level": self.level.pk, "session": self.session.pk})
        self.assertEqual(response.status_code, 200)
        # Resources are reusable level/subject materials, without a session field.
        # Existing learner policy is current level; historical evidence stays with
        # school management and the original assigned teacher, without a new grant.
        self.assertEqual([r["id"] for r in response.data["resources"]], [current.pk])
        self.enrollment.refresh_from_db()
        self.assertEqual((self.enrollment.class_arm_id, self.enrollment.session_id), (self.arm.pk, self.session.pk))
        self.assertEqual(AcademicResource.objects.filter(pk=self.approved.pk).values().get(), old)
        for role in ("teacher", "principal", "school_admin"):
            self.assertIn(self.approved.pk, [r["id"] for r in self.client_for(role).get("/api/curriculum/resources/").data["resources"]])

    def test_corrupt_resource_and_student_relations_do_not_disclose_foreign_content(self):
        corrupt = AcademicResource.objects.create(school=self.school, class_level=self.level, subject=self.foreign_subject,
            title="Corrupt foreign subject", kind="note", content="Foreign subject data", status="approved")
        for role, url in (("school_admin", "/api/curriculum/resources/"), ("student", "/api/curriculum/student-resources/")):
            response = self.client_for(role).get(url)
            self.assertNotIn(corrupt.pk, [r["id"] for r in response.data["resources"]])
        StudentProfile.objects.filter(pk=self.student.pk).update(school=self.other)
        self.assertEqual(self.client_for("student").get("/api/curriculum/student-resources/").status_code, 403)
