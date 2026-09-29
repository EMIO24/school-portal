"""Privacy regressions; reuse the existing academic/tenant readiness fixture."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import ParentStudentLink
from accounts import test_readiness
from enrollment.models import StaffProfile, StudentProfile, SubjectAssignment


class PrivacyTests(TestCase):
    client_for = test_readiness.ReadinessChecks.client_for

    @classmethod
    def setUpTestData(cls):
        test_readiness.ReadinessChecks.setUpTestData.__func__(cls)
        cls.profile = cls.other.student_profile
        cls.profile.religion = "Private demographic value"
        cls.profile.save(update_fields=["religion"])
        users = get_user_model().objects
        cls.peer = users.create_user(email="peer@privacy.invalid", role="student", school=cls.b, must_change_password=False)
        cls.peer_profile = StudentProfile.objects.create(user=cls.peer, school=cls.b, current_class=cls.arm)
        cls.parent = users.create_user(email="parent@privacy.invalid", role="parent", school=cls.b, must_change_password=False)
        ParentStudentLink.objects.create(parent=cls.parent, student=cls.profile, school=cls.b)
        cls.teacher = users.create_user(email="teacher@privacy.invalid", role="teacher", school=cls.b, must_change_password=False)
        cls.staff = StaffProfile.objects.create(user=cls.teacher, school=cls.b, religion="Private staff value", address="Private address")
        cls.term.is_current = True
        cls.term.save(update_fields=["is_current"])

    def test_administrators_manage_optional_religion_without_erasing_stored_values(self):
        client = self.client_for(self.admin, self.b)
        for path, profile in (("students", self.profile), ("staff", self.staff)):
            with self.subTest(path=path):
                url = f"/api/{path}/{profile.pk}/"
                original = profile.religion
                self.assertEqual(client.get(url).data["religion"], original)
                self.assertEqual(client.patch(url, {}, format="json").status_code, 200)
                profile.refresh_from_db()
                self.assertEqual(profile.religion, original)
                response = client.patch(url, {"religion": ""}, format="json")
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["religion"], "")
                response = client.post(f"/api/{path}/", {"new_email": f"new-{path}@privacy.invalid"}, format="json")
                self.assertEqual(response.status_code, 201, response.data)
                self.assertEqual(response.data["religion"], "")

    def test_teacher_student_detail_and_directories_omit_religion(self):
        client = self.client_for(self.teacher, self.b)
        for url in (f"/api/students/{self.profile.pk}/", "/api/students/", "/api/staff/",
                    f"/api/students/by-class/{self.arm.pk}/", "/api/staff/by-role/"):
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('"religion"', response.content.decode())
                self.assertNotIn("Private demographic value", response.content.decode())

    def test_staff_private_demographics_only_admin_or_self(self):
        url = f"/api/staff/{self.staff.pk}/"
        for user in (self.peer, self.parent):
            response = self.client_for(user, self.b).get(url)
            self.assertEqual(response.status_code, 200)
            for field in ("religion", "address", "dob", "phone", "state_of_origin"):
                self.assertNotIn(field, response.data)
        own = self.client_for(self.teacher, self.b).get(url)
        self.assertEqual(own.data["religion"], self.staff.religion)

    def test_student_details_deny_students_parents_and_foreign_users(self):
        for user in (self.peer, self.parent, self.student):
            response = self.client_for(user, self.b).get(f"/api/students/{self.profile.pk}/")
            self.assertIn(response.status_code, (403, 404))
        response = self.client_for(self.admin, self.a).get(f"/api/staff/{self.staff.pk}/")
        self.assertIn(response.status_code, (403, 404))

    def test_anonymous_cannot_enumerate_people_and_branding_stays_public_only(self):
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.b.slug)
        for url in ("/api/students/", "/api/staff/"):
            self.assertIn(client.get(url).status_code, (401, 403))
        response = client.get("/api/school/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"name", "slug", "subdomain", "logo", "theme", "motto", "entitlements"})

    def test_parent_and_student_results_require_relationship(self):
        self.entry.is_published = True
        self.entry.save()
        for user in (self.parent, self.other):
            client = self.client_for(user, self.b)
            own = client.get(f"/api/results/slip-data/{self.other.pk}/?term={self.term.pk}")
            self.assertEqual(own.status_code, 200)
            self.assertEqual(len(own.data["score_rows"]), 1)
            self.assertNotIn("religion", own.data)
            denied = client.get(f"/api/results/slip-data/{self.peer.pk}/?term={self.term.pk}")
            self.assertIn(denied.status_code, (403, 404))

    def test_documents_reject_unlinked_and_foreign_users_before_rendering(self):
        with patch("results.views._render_pdf") as render:
            for user, school in ((self.peer, self.b), (self.student, self.a), (self.admin, self.a)):
                response = self.client_for(user, school).get(f"/api/results/slip/{self.other.pk}/?term={self.term.pk}")
                self.assertIn(response.status_code, (403, 404))
            response = self.client_for(self.parent, self.b).get(f"/api/results/slip/{self.peer.pk}/?term={self.term.pk}")
            self.assertIn(response.status_code, (403, 404))
            render.assert_not_called()

    def test_parent_dashboard_hides_unpublished_scores_and_demographics(self):
        client = self.client_for(self.parent, self.b)
        response = client.get(f"/api/parent/dashboard/{self.profile.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Private demographic value", response.content.decode())
        self.assertNotIn('"religion"', response.content.decode())
        self.assertEqual(response.data["result_summary"]["subjects"], 0)
        self.assertIsNone(response.data["result_summary"]["average"])
        self.entry.is_published = True
        self.entry.save()
        published = client.get(f"/api/parent/dashboard/{self.profile.pk}/")
        self.assertEqual(published.data["result_summary"]["subjects"], 1)
        self.assertIn(client.get(f"/api/parent/dashboard/{self.peer_profile.pk}/").status_code, (403, 404))

    def test_assigned_teacher_can_edit_scores_unassigned_teacher_cannot(self):
        client = self.client_for(self.teacher, self.b)
        url = f"/api/gradebook/entries/{self.entry.pk}/"
        self.assertIn(client.patch(url, {"exam_score": 45}, format="json").status_code, (403, 404))
        SubjectAssignment.objects.create(school=self.b, teacher=self.staff, subject=self.subject,
                                        class_arm=self.arm, term=self.term, session=self.session)
        response = client.patch(url, {"exam_score": 45}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.entry.refresh_from_db()
        self.assertEqual(self.entry.exam_score, 45)

    def test_context_free_serializers_do_not_disclose_sensitive_demographics(self):
        from enrollment.serializers import StudentProfileSerializer
        from enrollment.staff_serializers import StaffProfileSerializer
        self.assertNotIn("religion", StudentProfileSerializer(self.profile).data)
        self.assertNotIn("religion", StaffProfileSerializer(self.staff).data)

    def test_enrollment_relations_cannot_expose_another_schools_records(self):
        from enrollment.models import ClassLevel, ClassArm, Subject
        level = ClassLevel.objects.create(school=self.a, name="JSS1")
        arm = ClassArm.objects.create(school=self.a, class_level=level, name="A")
        subject = Subject.objects.create(school=self.a, name="Private subject", code="PRIVATE")
        client = self.client_for(self.admin, self.b)
        for url, payload in ((f"/api/students/{self.profile.pk}/", {"current_class": arm.pk}),
                             (f"/api/staff/{self.staff.pk}/", {"assigned_classes": [arm.pk]}),
                             (f"/api/staff/{self.staff.pk}/", {"subjects_taught": [subject.pk]})):
            with self.subTest(payload=payload):
                self.assertEqual(client.patch(url, payload, format="json").status_code, 400)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.current_class_id, self.arm.pk)
        self.assertFalse(self.staff.assigned_classes.exists())
        self.assertFalse(self.staff.subjects_taught.exists())

    def test_platform_viewer_cannot_read_religion_or_change_it(self):
        from tenants.models import PlatformSecurity
        viewer = get_user_model().objects.create_user(email="viewer@privacy.invalid", role="superadmin", must_change_password=False)
        PlatformSecurity.objects.create(user=viewer, access_level="viewer")
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.b.slug)
        client.force_authenticate(viewer)
        response = client.get(f"/api/staff/{self.staff.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("religion", response.data)
        for path, profile in (("students", self.profile), ("staff", self.staff)):
            response = client.patch(f"/api/{path}/{profile.pk}/", {"religion": "changed"}, format="json")
            self.assertEqual(response.status_code, 403)
            profile.refresh_from_db()
            self.assertNotEqual(profile.religion, "changed")

    def test_own_login_profile_and_linked_children_omit_religion(self):
        for user, url in ((self.other, "/api/auth/me/"), (self.parent, "/api/parent/children/")):
            response = self.client_for(user, self.b).get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('"religion"', response.content.decode())
