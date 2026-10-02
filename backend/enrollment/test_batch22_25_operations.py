from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from academics.models import AcademicSession
from enrollment.models import (
    AdmissionApplication, ClassArm, ClassLevel, SessionEnrollment,
    StudentProfile, StudentRecordEntry, WelfareCase,
)
from tenants.models import Campus, School


class Batch22To25OperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        today = timezone.localdate()
        cls.school = School.objects.create(
            name="No Arm School",
            slug="no-arm-school",
            subdomain="no-arm-school",
            subscription_plan="enterprise",
            uses_class_arms=False,
        )
        cls.other_school = School.objects.create(
            name="Other School",
            slug="other-ops-school",
            subdomain="other-ops-school",
            subscription_plan="enterprise",
        )
        cls.session = AcademicSession.objects.create(
            school=cls.school,
            name="2026/2027",
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=300),
            is_current=True,
        )
        cls.level = ClassLevel.objects.create(
            school=cls.school, name="JSS1", order_index=1
        )
        User = get_user_model()
        cls.admin = User.objects.create_user(
            email="ops-admin@example.invalid",
            password="Pass1234!",
            first_name="Ada",
            last_name="Admin",
            role="school_admin",
            school=cls.school,
            must_change_password=False,
        )
        cls.principal = User.objects.create_user(
            email="ops-principal@example.invalid",
            password="Pass1234!",
            first_name="Priya",
            last_name="Principal",
            role="principal",
            school=cls.school,
            must_change_password=False,
        )
        cls.class_teacher = User.objects.create_user(
            email="ops-class@example.invalid",
            password="Pass1234!",
            first_name="Clara",
            last_name="Teacher",
            role="class_teacher",
            school=cls.school,
            must_change_password=False,
        )

    def client_for(self, user, school=None):
        school = school or self.school
        client = APIClient(HTTP_X_SCHOOL_SLUG=school.slug)
        token = RefreshToken.for_user(user).access_token
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(token))
        return client

    def create_application(self, **overrides):
        payload = {
            "first_name": "Mary",
            "last_name": "Learner",
            "guardian_name": "Grace Learner",
            "guardian_phone": "08000000000",
            "applying_class_level": self.level.pk,
        }
        payload.update(overrides)
        response = self.client_for(self.admin).post(
            "/api/operations/admissions/", payload, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_no_arm_admission_needs_no_fake_class_arm(self):
        app = self.create_application()
        decision = self.client_for(self.admin).post(
            f"/api/operations/admissions/{app['id']}/decision/",
            {"decision": "admit"},
            format="json",
        )
        self.assertEqual(decision.status_code, 201, decision.data)
        student = StudentProfile.objects.get(pk=decision.data["admitted_student"])
        self.assertIsNotNone(student.current_class)
        self.assertTrue(student.current_class.is_default)
        self.assertEqual(student.current_class.name, "")
        self.assertEqual(student.current_class.full_name, "JSS1")
        enrollment = SessionEnrollment.objects.get(
            school=self.school, student=student, session=self.session, status="active"
        )
        self.assertEqual(enrollment.class_arm, student.current_class)

    def test_no_arm_multi_campus_admission_uses_campus_default_class(self):
        campus = Campus.objects.create(
            school=self.school, name="West Campus", code="WEST", is_primary=True
        )
        app = self.create_application(preferred_campus=campus.pk)
        decision = self.client_for(self.principal).post(
            f"/api/operations/admissions/{app['id']}/decision/",
            {"decision": "admit"},
            format="json",
        )
        self.assertEqual(decision.status_code, 201, decision.data)
        student = StudentProfile.objects.get(pk=decision.data["admitted_student"])
        self.assertEqual(student.current_class.campus_id, campus.pk)
        self.assertTrue(student.current_class.is_default)
        self.assertEqual(student.current_class.full_name, "JSS1")

    def test_named_arm_school_requires_destination_arm(self):
        named = School.objects.create(
            name="Named Arm School",
            slug="named-arm-school",
            subdomain="named-arm-school",
            subscription_plan="basic",
            uses_class_arms=True,
        )
        AcademicSession.objects.create(
            school=named,
            name="2026/2027",
            start_date=timezone.localdate() - timedelta(days=10),
            end_date=timezone.localdate() + timedelta(days=300),
            is_current=True,
        )
        level = ClassLevel.objects.create(school=named, name="JSS1", order_index=1)
        User = get_user_model()
        admin = User.objects.create_user(
            email="named-admin@example.invalid", password="Pass1234!",
            first_name="Named", last_name="Admin", role="school_admin",
            school=named, must_change_password=False,
        )
        client = self.client_for(admin, named)
        created = client.post("/api/operations/admissions/", {
            "first_name": "Arm",
            "last_name": "Required",
            "guardian_name": "Guardian",
            "guardian_phone": "0800",
            "applying_class_level": level.pk,
        }, format="json")
        self.assertEqual(created.status_code, 201)
        decision = client.post(
            f"/api/operations/admissions/{created.data['id']}/decision/",
            {"decision": "admit"},
            format="json",
        )
        self.assertEqual(decision.status_code, 400)
        self.assertIn("class_arm", decision.data)

    def test_official_records_are_append_only_and_corrections_are_explicit(self):
        app = self.create_application()
        admitted = self.client_for(self.admin).post(
            f"/api/operations/admissions/{app['id']}/decision/",
            {"decision": "admit"},
            format="json",
        )
        student_id = admitted.data["admitted_student"]
        history = self.client_for(self.admin).get(
            f"/api/operations/student-records/{student_id}/"
        )
        self.assertEqual(history.status_code, 200)
        self.assertEqual(len(history.data), 1)
        original = history.data[0]

        correction = self.client_for(self.principal).post(
            f"/api/operations/student-records/{student_id}/",
            {
                "kind": "identity",
                "title": "Correct guardian surname",
                "details": "Verified against supplied identity document.",
                "effective_date": timezone.localdate().isoformat(),
                "supersedes": original["id"],
            },
            format="json",
        )
        self.assertEqual(correction.status_code, 201, correction.data)
        self.assertEqual(correction.data["supersedes"], original["id"])
        self.assertEqual(
            StudentRecordEntry.objects.filter(student_id=student_id).count(), 2
        )

    def test_class_teacher_welfare_scope_excludes_sensitive_cases(self):
        arm = ClassArm.objects.create(
            school=self.school, class_level=self.level,
            name="", is_default=True, class_teacher=self.class_teacher,
        )
        User = get_user_model()
        student_user = User.objects.create_user(
            email="welfare-student@example.invalid",
            password="Pass1234!",
            first_name="Wale",
            last_name="Student",
            role="student",
            school=self.school,
            must_change_password=False,
        )
        student = StudentProfile.objects.create(
            user=student_user, school=self.school, current_class=arm, status="active"
        )
        teacher = self.client_for(self.class_teacher)
        ordinary = teacher.post("/api/operations/welfare/", {
            "student": student.pk,
            "category": "attendance",
            "severity": "medium",
            "title": "Repeated lateness",
            "details": "Three late arrivals this week.",
        }, format="json")
        self.assertEqual(ordinary.status_code, 201, ordinary.data)

        restricted = teacher.post("/api/operations/welfare/", {
            "student": student.pk,
            "category": "safeguarding",
            "severity": "high",
            "title": "Sensitive concern",
            "details": "Restricted case.",
        }, format="json")
        self.assertEqual(restricted.status_code, 403)

        manager = self.client_for(self.principal).post("/api/operations/welfare/", {
            "student": student.pk,
            "category": "safeguarding",
            "severity": "high",
            "title": "Sensitive concern",
            "details": "Restricted case.",
        }, format="json")
        self.assertEqual(manager.status_code, 201)
        visible = teacher.get("/api/operations/welfare/")
        self.assertEqual(visible.status_code, 200)
        self.assertEqual([row["category"] for row in visible.data], ["attendance"])
        self.assertEqual(WelfareCase.objects.filter(school=self.school).count(), 2)

    def test_enterprise_campus_creation_provisions_no_arm_classes(self):
        response = self.client_for(self.admin).post("/api/campuses/", {
            "name": "East Campus",
            "code": "EAST",
            "is_primary": True,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        campus = Campus.objects.get(pk=response.data["id"])
        implicit = ClassArm.objects.get(
            school=self.school, campus=campus, class_level=self.level, is_default=True
        )
        self.assertEqual(implicit.full_name, "JSS1")

        listing = self.client_for(self.admin).get("/api/campuses/")
        self.assertEqual(listing.status_code, 200)
        row = next(item for item in listing.data if item["id"] == campus.pk)
        self.assertEqual(row["class_count"], 1)
