from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from curriculum.models import AcademicResource
from enrollment.models import ClassArm, ClassLevel, StudentProfile, Subject
from tenants.models import School


class Batch24LearningDeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(
            name="Learning Delivery School",
            slug="learning-delivery-school",
            subdomain="learning-delivery-school",
            subscription_plan="premium",
        )
        cls.other_school = School.objects.create(
            name="Other Learning School",
            slug="other-learning-school",
            subdomain="other-learning-school",
            subscription_plan="premium",
        )
        cls.level = ClassLevel.objects.create(school=cls.school, name="JSS1", order_index=1)
        cls.arm = ClassArm.objects.create(school=cls.school, class_level=cls.level, name="A")
        cls.subject = Subject.objects.create(
            school=cls.school, name="Mathematics", code="MTH",
            category="core", max_ca_score=40, max_exam_score=60,
        )
        cls.subject.class_levels.add(cls.level)
        User = get_user_model()
        cls.student_user = User.objects.create_user(
            email="resource-student@example.invalid", password="Pass1234!",
            first_name="Resource", last_name="Student", role="student",
            school=cls.school, must_change_password=False,
        )
        cls.student = StudentProfile.objects.create(
            user=cls.student_user, school=cls.school, current_class=cls.arm, status="active"
        )
        cls.approved = AcademicResource.objects.create(
            school=cls.school, class_level=cls.level, subject=cls.subject,
            title="Fractions note", kind="note", content="Approved content",
            status=AcademicResource.Status.APPROVED,
        )
        cls.draft = AcademicResource.objects.create(
            school=cls.school, class_level=cls.level, subject=cls.subject,
            title="Draft note", kind="note", content="Draft content",
            status=AcademicResource.Status.DRAFT,
        )

    def client_for(self, user, school=None):
        school = school or self.school
        client = APIClient(HTTP_X_SCHOOL_SLUG=school.slug)
        client.credentials(
            HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(user).access_token)
        )
        return client

    def test_student_sees_only_approved_resources_for_current_level(self):
        response = self.client_for(self.student_user).get(
            "/api/curriculum/student-resources/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["id"] for row in response.data["resources"]],
            [self.approved.pk],
        )

    def test_student_resource_endpoint_is_tenant_bound(self):
        response = self.client_for(self.student_user, self.other_school).get(
            "/api/curriculum/student-resources/"
        )
        self.assertEqual(response.status_code, 403)
