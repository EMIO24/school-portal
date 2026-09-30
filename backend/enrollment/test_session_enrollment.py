from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import CustomUser
from academics.models import AcademicSession
from tenants.models import School
from .models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile


class SessionEnrollmentTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Enrollment School", slug="enrollment-school",
            subdomain="enrollment-school"
        )
        self.other = School.objects.create(
            name="Other Enrollment School", slug="other-enrollment-school",
            subdomain="other-enrollment-school"
        )
        self.user = CustomUser.objects.create_user(
            "student@enrollment.test", "Password!123",
            school=self.school, role="student"
        )
        self.level = ClassLevel.objects.create(
            school=self.school, name="JSS1", order_index=1
        )
        self.arm = ClassArm.objects.create(
            school=self.school, class_level=self.level, name="A"
        )
        self.student = StudentProfile.objects.create(
            school=self.school, user=self.user, current_class=self.arm,
            admission_number="ENR001"
        )
        self.session = AcademicSession.objects.create(
            school=self.school, name="2026/27",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31),
            is_current=True
        )

    def create_enrollment(self, **overrides):
        values = {
            "school": self.school,
            "student": self.student,
            "session": self.session,
            "class_arm": self.arm,
            "status": "active",
            "entry_reason": "migration",
            "enrolled_on": date(2026, 9, 1),
        }
        values.update(overrides)
        return SessionEnrollment.objects.create(**values)

    def test_records_historical_class_without_replacing_current_class(self):
        enrollment = self.create_enrollment()
        self.student.refresh_from_db()
        self.assertEqual(enrollment.class_arm, self.arm)
        self.assertEqual(enrollment.session, self.session)
        self.assertEqual(self.student.current_class, self.arm)
        self.assertEqual(enrollment.class_name, "JSS1A")

    def test_student_can_have_multiple_periods_but_only_one_active_per_session(self):
        first = self.create_enrollment(
            status="transferred",
            exited_on=date(2026, 12, 31),
        )
        second = self.create_enrollment(
            enrolled_on=date(2027, 1, 1),
            entry_reason="transfer",
        )
        self.assertNotEqual(first.pk, second.pk)

        with self.assertRaises(ValidationError):
            self.create_enrollment(
                enrolled_on=date(2027, 2, 1),
                entry_reason="manual",
            )

        # The partial database constraint also survives paths that bypass model.save().
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionEnrollment.objects.bulk_create([
                    SessionEnrollment(
                        school=self.school,
                        student=self.student,
                        session=self.session,
                        class_arm=self.arm,
                        enrolled_on=date(2027, 2, 1),
                    )
                ])

    def test_overlapping_closed_periods_are_rejected(self):
        self.create_enrollment(
            status="transferred",
            exited_on=date(2026, 12, 31),
        )
        with self.assertRaises(ValidationError):
            self.create_enrollment(
                status="completed",
                enrolled_on=date(2026, 12, 15),
                exited_on=date(2027, 1, 15),
            )

    def test_cross_tenant_student_session_or_class_is_rejected(self):
        other_level = ClassLevel.objects.create(
            school=self.other, name="JSS1", order_index=1
        )
        other_arm = ClassArm.objects.create(
            school=self.other, class_level=other_level, name="A"
        )
        other_session = AcademicSession.objects.create(
            school=self.other, name="2026/27",
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 31)
        )

        with self.assertRaises(ValidationError):
            self.create_enrollment(school=self.other)
        with self.assertRaises(ValidationError):
            self.create_enrollment(session=other_session)
        with self.assertRaises(ValidationError):
            self.create_enrollment(class_arm=other_arm)

    def test_enrollment_and_exit_dates_must_belong_to_session(self):
        with self.assertRaises(ValidationError):
            self.create_enrollment(enrolled_on=date(2026, 8, 31))
        with self.assertRaises(ValidationError):
            self.create_enrollment(enrolled_on=date(2027, 8, 1))
        with self.assertRaises(ValidationError):
            self.create_enrollment(
                status="completed",
                exited_on=date(2027, 8, 1),
            )

    def test_active_and_closed_statuses_have_consistent_exit_dates(self):
        with self.assertRaises(ValidationError):
            self.create_enrollment(exited_on=date(2027, 7, 1))

        with self.assertRaises(ValidationError):
            self.create_enrollment(status="completed")

        enrollment = self.create_enrollment(
            status="completed",
            exited_on=date(2027, 7, 31),
        )
        self.assertEqual(enrollment.status, "completed")
        self.assertEqual(enrollment.exited_on, date(2027, 7, 31))

    def test_database_rejects_exit_before_entry_when_validation_is_bypassed(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SessionEnrollment.objects.bulk_create([
                    SessionEnrollment(
                        school=self.school,
                        student=self.student,
                        session=self.session,
                        class_arm=self.arm,
                        status="completed",
                        enrolled_on=date(2026, 9, 10),
                        exited_on=date(2026, 9, 9),
                    )
                ])
