from datetime import date

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import CustomUser
from academics.models import AcademicSession
from tenants.models import School

from .migration_import import assess, create
from .models import (
    ClassArm,
    ClassLevel,
    MigrationStudentReference,
    SessionEnrollment,
    StudentProfile,
)
from .serializers import StudentProfileSerializer
from .session_enrollment import EnrollmentPlacementError, ensure_current_enrollment
from .views import StudentViewSet


class CurrentEnrollmentWorkflowTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Enrollment Workflow School",
            slug="enrollment-workflow",
            subdomain="enrollment-workflow",
        )
        self.other = School.objects.create(
            name="Other Enrollment Workflow School",
            slug="other-enrollment-workflow",
            subdomain="other-enrollment-workflow",
        )
        self.admin = CustomUser.objects.create_user(
            "admin@workflow.test",
            "Password!123",
            school=self.school,
            role="school_admin",
        )
        self.level1 = ClassLevel.objects.create(
            school=self.school, name="JSS1", order_index=1
        )
        self.level2 = ClassLevel.objects.create(
            school=self.school, name="JSS2", order_index=2
        )
        self.arm1 = ClassArm.objects.create(
            school=self.school, class_level=self.level1, name="A"
        )
        self.arm2 = ClassArm.objects.create(
            school=self.school, class_level=self.level2, name="A"
        )
        self.session = AcademicSession.objects.create(
            school=self.school,
            name="2026/27",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_current=True,
        )
        self.factory = APIRequestFactory()

    def request(self, method="post", path="/api/students/"):
        maker = getattr(self.factory, method)
        request = maker(path, {}, format="json")
        request.tenant = self.school
        force_authenticate(request, self.admin)
        return request

    def create_student(self, email="student@workflow.test", current_class=None):
        user = CustomUser.objects.create_user(
            email,
            "Password!123",
            school=self.school,
            role="student",
        )
        return StudentProfile.objects.create(
            school=self.school,
            user=user,
            current_class=current_class,
            admission_number=f"WF{user.pk:04d}",
        )

    def test_admission_with_class_creates_authoritative_enrollment(self):
        request = self.request()
        serializer = StudentProfileSerializer(
            data={
                "new_email": "newstudent@workflow.test",
                "new_first_name": "Ada",
                "new_last_name": "Student",
                "current_class": self.arm1.pk,
                "status": "active",
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        student = serializer.save(school=self.school)
        enrollment = SessionEnrollment.objects.get(
            student=student, session=self.session
        )

        self.assertEqual(student.current_class_id, self.arm1.pk)
        self.assertEqual(enrollment.class_arm_id, self.arm1.pk)
        self.assertEqual(enrollment.entry_reason, "admission")
        self.assertEqual(enrollment.status, "active")
        self.assertEqual(enrollment.created_by, self.admin)

    def test_admission_without_class_creates_no_enrollment(self):
        request = self.request()
        serializer = StudentProfileSerializer(
            data={
                "new_email": "unassigned@workflow.test",
                "new_first_name": "Unassigned",
                "new_last_name": "Student",
                "status": "active",
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        student = serializer.save(school=self.school)

        self.assertIsNone(student.current_class_id)
        self.assertFalse(
            SessionEnrollment.objects.filter(student=student).exists()
        )

    def test_admission_with_class_fails_without_current_session_and_rolls_back(self):
        self.session.is_current = False
        self.session.save(update_fields=["is_current"])
        request = self.request()
        serializer = StudentProfileSerializer(
            data={
                "new_email": "nosession@workflow.test",
                "new_first_name": "No",
                "new_last_name": "Session",
                "current_class": self.arm1.pk,
                "status": "active",
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

        with self.assertRaises(Exception):
            serializer.save(school=self.school)

        self.assertFalse(
            CustomUser.objects.filter(email="nosession@workflow.test").exists()
        )
        self.assertFalse(
            StudentProfile.objects.filter(
                user__email="nosession@workflow.test"
            ).exists()
        )

    def test_profile_patch_cannot_bypass_controlled_class_assignment(self):
        student = self.create_student(current_class=self.arm1)
        request = self.request(method="patch", path=f"/api/students/{student.pk}/")
        serializer = StudentProfileSerializer(
            student,
            data={"current_class": self.arm2.pk},
            partial=True,
            context={"request": request},
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("current_class", serializer.errors)

    def test_initial_assign_class_creates_manual_enrollment(self):
        student = self.create_student(current_class=None)
        request = self.factory.post(
            f"/api/students/{student.pk}/assign-class/",
            {"class_arm": self.arm1.pk},
            format="json",
        )
        request.tenant = self.school
        force_authenticate(request, self.admin)

        response = StudentViewSet.as_view({"post": "assign_class"})(
            request, pk=student.pk
        )

        self.assertEqual(response.status_code, 200)
        student.refresh_from_db()
        enrollment = SessionEnrollment.objects.get(
            student=student, session=self.session
        )
        self.assertEqual(student.current_class_id, self.arm1.pk)
        self.assertEqual(enrollment.class_arm_id, self.arm1.pk)
        self.assertEqual(enrollment.entry_reason, "manual")

    def test_same_class_assignment_is_idempotent(self):
        student = self.create_student(current_class=self.arm1)
        first, created = ensure_current_enrollment(
            school=self.school,
            student=student,
            class_arm=self.arm1,
            actor=self.admin,
            entry_reason="manual",
        )
        self.assertTrue(created)

        second, created_again = ensure_current_enrollment(
            school=self.school,
            student=student,
            class_arm=self.arm1,
            actor=self.admin,
            entry_reason="manual",
        )

        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            SessionEnrollment.objects.filter(
                student=student, session=self.session
            ).count(),
            1,
        )

    def test_different_class_assignment_is_blocked_without_rewriting_history(self):
        student = self.create_student(current_class=self.arm1)
        enrollment, _ = ensure_current_enrollment(
            school=self.school,
            student=student,
            class_arm=self.arm1,
            actor=self.admin,
            entry_reason="manual",
        )

        with self.assertRaises(EnrollmentPlacementError):
            ensure_current_enrollment(
                school=self.school,
                student=student,
                class_arm=self.arm2,
                actor=self.admin,
                entry_reason="manual",
            )

        enrollment.refresh_from_db()
        student.refresh_from_db()
        self.assertEqual(enrollment.class_arm_id, self.arm1.pk)
        self.assertEqual(student.current_class_id, self.arm1.pk)

    def test_inactive_student_cannot_be_silently_reenrolled(self):
        student = self.create_student(current_class=None)
        student.status = "graduated"
        student.save(update_fields=["status"])

        with self.assertRaises(EnrollmentPlacementError):
            ensure_current_enrollment(
                school=self.school,
                student=student,
                class_arm=self.arm1,
                actor=self.admin,
                entry_reason="manual",
            )

        self.assertFalse(
            SessionEnrollment.objects.filter(student=student).exists()
        )

    def test_foreign_school_class_is_rejected(self):
        other_level = ClassLevel.objects.create(
            school=self.other, name="JSS1", order_index=1
        )
        other_arm = ClassArm.objects.create(
            school=self.other, class_level=other_level, name="A"
        )
        student = self.create_student(current_class=None)

        with self.assertRaises(EnrollmentPlacementError):
            ensure_current_enrollment(
                school=self.school,
                student=student,
                class_arm=other_arm,
                actor=self.admin,
                entry_reason="manual",
            )

    def test_migration_centre_student_create_writes_session_enrollment(self):
        row = {
            "student_ref": "LEGACY-001",
            "first_name": "Legacy",
            "last_name": "Student",
            "class_level": "JSS1",
            "class_arm": "A",
            "email": "legacy@workflow.test",
            "dob": "2014-01-10",
            "gender": "female",
            "state_of_origin": "",
            "guardian_name": "Guardian",
            "guardian_phone": "08000000000",
            "guardian_email": "",
            "guardian_relationship": "guardian",
        }
        action, data = assess(
            "students",
            row,
            self.school,
            current_session=self.session,
        )
        self.assertEqual(action, "CREATE")
        data["actor"] = self.admin

        create("students", row, self.school, data)

        identity = MigrationStudentReference.objects.get(
            school=self.school, reference="LEGACY-001"
        )
        enrollment = SessionEnrollment.objects.get(
            student=identity.student, session=self.session
        )
        self.assertEqual(enrollment.class_arm_id, self.arm1.pk)
        self.assertEqual(enrollment.entry_reason, "admission")
        self.assertEqual(identity.student.current_class_id, self.arm1.pk)
