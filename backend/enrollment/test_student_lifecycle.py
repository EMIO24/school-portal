from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import CustomUser
from academics.models import AcademicSession
from tenants.models import PlatformEvent, School

from .lifecycle import StudentLifecycleError, transition_student
from .models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile
from .serializers import StudentProfileSerializer
from .views import StudentViewSet


class StudentLifecycleTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Lifecycle School",
            slug="lifecycle-school",
            subdomain="lifecycle-school",
        )
        self.other = School.objects.create(
            name="Other Lifecycle School",
            slug="other-lifecycle-school",
            subdomain="other-lifecycle-school",
        )
        self.admin = CustomUser.objects.create_user(
            "admin@lifecycle.test",
            "Password!123",
            school=self.school,
            role="school_admin",
        )
        self.student_user = CustomUser.objects.create_user(
            "student@lifecycle.test",
            "Password!123",
            school=self.school,
            role="student",
        )
        self.level = ClassLevel.objects.create(
            school=self.school, name="JSS1", order_index=1
        )
        self.arm = ClassArm.objects.create(
            school=self.school, class_level=self.level, name="A"
        )
        self.session = AcademicSession.objects.create(
            school=self.school,
            name="2026/27",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_current=True,
        )
        self.student = StudentProfile.objects.create(
            school=self.school,
            user=self.student_user,
            current_class=self.arm,
            admission_number="LIFE001",
        )
        self.enrollment = SessionEnrollment.objects.create(
            school=self.school,
            student=self.student,
            session=self.session,
            class_arm=self.arm,
            status="active",
            entry_reason="admission",
            enrolled_on=self.session.start_date,
            created_by=self.admin,
        )
        self.factory = APIRequestFactory()

    def test_suspend_retains_enrollment_and_class_but_disables_login(self):
        transition_student(
            school=self.school,
            student=self.student,
            action="suspend",
            actor=self.admin,
            reason="Disciplinary review",
        )
        self.student.refresh_from_db()
        self.student_user.refresh_from_db()
        self.enrollment.refresh_from_db()

        self.assertEqual(self.student.status, "suspended")
        self.assertEqual(self.student.current_class_id, self.arm.pk)
        self.assertEqual(self.enrollment.status, "active")
        self.assertIsNone(self.enrollment.exited_on)
        self.assertFalse(self.student_user.is_active)
        self.assertTrue(
            PlatformEvent.objects.filter(
                action="school.student_suspended",
                target=str(self.student.pk),
            ).exists()
        )

    def test_suspended_student_can_reactivate_with_matching_active_enrollment(self):
        transition_student(
            school=self.school,
            student=self.student,
            action="suspend",
            actor=self.admin,
        )
        transition_student(
            school=self.school,
            student=self.student,
            action="reactivate",
            actor=self.admin,
        )

        self.student.refresh_from_db()
        self.student_user.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.student.status, "active")
        self.assertTrue(self.student_user.is_active)
        self.assertEqual(self.enrollment.status, "active")
        self.assertEqual(self.student.current_class_id, self.arm.pk)

    def test_reactivation_fails_if_current_enrollment_is_missing(self):
        self.student.status = "suspended"
        self.student.save(update_fields=["status"])
        self.student_user.is_active = False
        self.student_user.save(update_fields=["is_active"])
        self.enrollment.delete()

        with self.assertRaises(StudentLifecycleError):
            transition_student(
                school=self.school,
                student=self.student,
                action="reactivate",
                actor=self.admin,
            )

        self.student.refresh_from_db()
        self.student_user.refresh_from_db()
        self.assertEqual(self.student.status, "suspended")
        self.assertFalse(self.student_user.is_active)

    def test_withdrawal_closes_enrollment_clears_class_and_disables_login(self):
        effective = timezone.localdate()
        transition_student(
            school=self.school,
            student=self.student,
            action="withdraw",
            actor=self.admin,
            effective_date=effective,
            reason="Relocated",
        )

        self.student.refresh_from_db()
        self.student_user.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.student.status, "withdrawn")
        self.assertIsNone(self.student.current_class)
        self.assertEqual(self.enrollment.status, "withdrawn")
        self.assertEqual(self.enrollment.exited_on, effective)
        self.assertFalse(self.student_user.is_active)
        self.assertIn("Relocated", self.enrollment.notes)

    def test_suspended_student_can_be_withdrawn(self):
        transition_student(
            school=self.school,
            student=self.student,
            action="suspend",
            actor=self.admin,
        )
        transition_student(
            school=self.school,
            student=self.student,
            action="withdraw",
            actor=self.admin,
            effective_date=timezone.localdate(),
        )
        self.student.refresh_from_db()
        self.assertEqual(self.student.status, "withdrawn")

    def test_withdrawn_or_graduated_student_cannot_reactivate_directly(self):
        for status in ("withdrawn", "graduated"):
            self.student.status = status
            self.student.save(update_fields=["status"])
            with self.assertRaises(StudentLifecycleError):
                transition_student(
                    school=self.school,
                    student=self.student,
                    action="reactivate",
                    actor=self.admin,
                )

    def test_future_or_pre_enrollment_withdrawal_date_is_rejected(self):
        for invalid in (
            timezone.localdate() + timedelta(days=1),
            self.enrollment.enrolled_on - timedelta(days=1),
        ):
            with self.assertRaises(StudentLifecycleError):
                transition_student(
                    school=self.school,
                    student=self.student,
                    action="withdraw",
                    actor=self.admin,
                    effective_date=invalid,
                )
            self.enrollment.refresh_from_db()
            self.assertEqual(self.enrollment.status, "active")

    def test_foreign_school_student_cannot_transition(self):
        with self.assertRaises(StudentLifecycleError):
            transition_student(
                school=self.other,
                student=self.student,
                action="suspend",
                actor=self.admin,
            )

    def test_direct_profile_patch_cannot_change_status(self):
        request = self.factory.patch(
            f"/api/students/{self.student.pk}/",
            {"status": "withdrawn"},
            format="json",
        )
        request.tenant = self.school
        force_authenticate(request, self.admin)
        serializer = StudentProfileSerializer(
            self.student,
            data={"status": "withdrawn"},
            partial=True,
            context={"request": request},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("status", serializer.errors)

    def test_lifecycle_endpoint_is_admin_controlled_and_returns_updated_student(self):
        request = self.factory.post(
            f"/api/students/{self.student.pk}/lifecycle/",
            {"action": "suspend", "reason": "Temporary"},
            format="json",
        )
        request.tenant = self.school
        force_authenticate(request, self.admin)

        response = StudentViewSet.as_view({"post": "lifecycle"})(
            request, pk=self.student.pk
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "suspended")

    def test_invalid_lifecycle_action_is_rejected_without_state_change(self):
        with self.assertRaises(StudentLifecycleError):
            transition_student(
                school=self.school,
                student=self.student,
                action="graduate-now",
                actor=self.admin,
            )
        self.student.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.student.status, "active")
        self.assertEqual(self.enrollment.status, "active")
