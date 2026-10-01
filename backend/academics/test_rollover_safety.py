from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser
from attendance.models import AttendanceSession
from enrollment.models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile
from tenants.models import School

from .models import AcademicRollover, AcademicSession, Term


class AcademicRolloverSafetyTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name="Rollover School", slug="rollover", subdomain="rollover")
        self.other = School.objects.create(name="Other School", slug="other-rollover", subdomain="other-rollover")
        self.admin = CustomUser.objects.create_user(
            "admin@rollover.test", "Password!123", school=self.school, role="school_admin"
        )
        self.student_user = CustomUser.objects.create_user(
            "student@rollover.test", "Password!123", school=self.school, role="student"
        )
        self.level = ClassLevel.objects.create(school=self.school, name="JSS1", order_index=1)
        self.arm = ClassArm.objects.create(school=self.school, class_level=self.level, name="A")
        self.student = StudentProfile.objects.create(
            school=self.school, user=self.student_user, current_class=self.arm
        )

        self.source = AcademicSession.objects.create(
            school=self.school,
            name="2026/27",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_current=True,
        )
        self.source_term = Term.objects.create(
            session=self.source,
            name="first",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 18),
            is_current=True,
        )
        self.destination = AcademicSession.objects.create(
            school=self.school,
            name="2027/28",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 7, 31),
        )
        self.destination_term = Term.objects.create(
            session=self.destination,
            name="first",
            start_date=date(2027, 9, 1),
            end_date=date(2027, 12, 17),
        )
        self.enrollment = SessionEnrollment.objects.create(
            school=self.school,
            student=self.student,
            session=self.source,
            class_arm=self.arm,
            status="active",
            entry_reason="admission",
            enrolled_on=date(2026, 10, 1),
            created_by=self.admin,
        )
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def test_direct_session_activation_is_blocked_while_source_has_active_placements(self):
        response = self.client.post(f"/api/sessions/{self.destination.pk}/set-current/", format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.source.refresh_from_db()
        self.destination.refresh_from_db()
        self.assertTrue(self.source.is_current)
        self.assertFalse(self.destination.is_current)

    def test_term_activation_cannot_bypass_session_rollover_guard(self):
        response = self.client.post(f"/api/terms/{self.destination_term.pk}/set-current/", format="json")
        self.assertEqual(response.status_code, 400, response.data)
        self.source_term.refresh_from_db()
        self.destination_term.refresh_from_db()
        self.assertTrue(self.source_term.is_current)
        self.assertFalse(self.destination_term.is_current)

    def test_completed_source_placement_allows_safe_cutover_and_activates_first_term(self):
        self.enrollment.status = "completed"
        self.enrollment.exited_on = self.source.end_date
        self.enrollment.save()
        SessionEnrollment.objects.create(
            school=self.school,
            student=self.student,
            session=self.destination,
            class_arm=self.arm,
            status="active",
            entry_reason="promotion",
            enrolled_on=self.destination.start_date,
            created_by=self.admin,
        )

        response = self.client.post(f"/api/sessions/{self.destination.pk}/set-current/", format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.source.refresh_from_db()
        self.destination.refresh_from_db()
        self.source_term.refresh_from_db()
        self.destination_term.refresh_from_db()
        self.assertFalse(self.source.is_current)
        self.assertTrue(self.destination.is_current)
        self.assertFalse(self.source_term.is_current)
        self.assertTrue(self.destination_term.is_current)

    def test_database_rejects_two_current_sessions_when_model_guard_is_bypassed(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AcademicSession.objects.filter(pk=self.destination.pk).update(is_current=True)

    def test_session_creation_rejects_overlap(self):
        response = self.client.post(
            "/api/sessions/",
            {
                "name": "Overlap",
                "start_date": "2027-07-01",
                "end_date": "2027-10-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_term_creation_rejects_dates_outside_session(self):
        response = self.client.post(
            "/api/terms/",
            {
                "session": self.destination.pk,
                "name": "second",
                "start_date": "2027-08-01",
                "end_date": "2027-11-30",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_session_dates_are_frozen_after_enrollment_history_exists(self):
        response = self.client.patch(
            f"/api/sessions/{self.source.pk}/",
            {"end_date": "2027-08-15"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.source.refresh_from_db()
        self.assertEqual(self.source.end_date, date(2027, 7, 31))

    def test_term_dates_are_frozen_after_execution_history_exists(self):
        AttendanceSession.objects.create(
            school=self.school,
            class_arm=self.arm,
            term=self.source_term,
            date=date(2026, 10, 1),
            mode="daily",
        )
        response = self.client.patch(
            f"/api/terms/{self.source_term.pk}/",
            {"end_date": "2026-12-17"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.source_term.refresh_from_db()
        self.assertEqual(self.source_term.end_date, date(2026, 12, 18))

    def test_rollover_state_rejects_cross_tenant_or_nonsequential_sessions(self):
        other_session = AcademicSession.objects.create(
            school=self.other,
            name="2027/28",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 7, 31),
        )
        with self.assertRaises(ValidationError):
            AcademicRollover.objects.create(
                school=self.school,
                source_session=self.source,
                destination_session=other_session,
                created_by=self.admin,
            )
        with self.assertRaises(ValidationError):
            AcademicRollover.objects.create(
                school=self.school,
                source_session=self.source,
                destination_session=self.source,
                created_by=self.admin,
            )

    def test_completed_rollover_requires_completion_timestamp_and_is_unique(self):
        with self.assertRaises(ValidationError):
            AcademicRollover.objects.create(
                school=self.school,
                source_session=self.source,
                destination_session=self.destination,
                status="completed",
                created_by=self.admin,
            )
        AcademicRollover.objects.create(
            school=self.school,
            source_session=self.source,
            destination_session=self.destination,
            status="completed",
            completed_at=timezone.now(),
            created_by=self.admin,
            completed_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            AcademicRollover.objects.create(
                school=self.school,
                source_session=self.source,
                destination_session=self.destination,
                status="completed",
                completed_at=timezone.now(),
                created_by=self.admin,
                completed_by=self.admin,
            )
