from datetime import date

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from academics.models import AcademicSession
from tenants.models import PlatformEvent, School

from .models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile
from .transfers import StudentTransferError, transfer_student


class StudentTransferTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Transfer School",
            slug="transfer-school",
            subdomain="transfer-school",
        )
        self.other = School.objects.create(
            name="Other Transfer School",
            slug="other-transfer-school",
            subdomain="other-transfer-school",
        )
        self.admin = CustomUser.objects.create_user(
            "admin@transfer.test", "Password!123",
            school=self.school, role="school_admin",
        )
        self.user = CustomUser.objects.create_user(
            "student@transfer.test", "Password!123",
            school=self.school, role="student",
        )
        self.level1 = ClassLevel.objects.create(
            school=self.school, name="JSS1", order_index=1,
        )
        self.level2 = ClassLevel.objects.create(
            school=self.school, name="JSS2", order_index=2,
        )
        self.arm_a = ClassArm.objects.create(
            school=self.school, class_level=self.level1, name="A",
        )
        self.arm_b = ClassArm.objects.create(
            school=self.school, class_level=self.level1, name="B",
        )
        self.arm_jss2 = ClassArm.objects.create(
            school=self.school, class_level=self.level2, name="A",
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
            user=self.user,
            current_class=self.arm_a,
            admission_number="TRN001",
        )
        self.source = SessionEnrollment.objects.create(
            school=self.school,
            student=self.student,
            session=self.session,
            class_arm=self.arm_a,
            status="active",
            entry_reason="admission",
            enrolled_on=date(2026, 9, 1),
            created_by=self.admin,
        )
        self.effective = date(2026, 9, 15)

    def transfer(self, destination=None, effective=None):
        return transfer_student(
            school=self.school,
            student=self.student,
            destination_class=destination or self.arm_b,
            effective_date=effective or self.effective,
            actor=self.admin,
            reason="Class balancing",
        )

    def test_transfer_preserves_source_and_creates_active_destination_period(self):
        student, source, destination = self.transfer()
        source.refresh_from_db()
        destination.refresh_from_db()
        student.refresh_from_db()

        self.assertEqual(source.status, "transferred")
        self.assertEqual(source.exited_on, date(2026, 9, 14))
        self.assertEqual(source.class_arm, self.arm_a)
        self.assertEqual(destination.status, "active")
        self.assertEqual(destination.entry_reason, "transfer")
        self.assertEqual(destination.enrolled_on, self.effective)
        self.assertEqual(destination.class_arm, self.arm_b)
        self.assertEqual(student.current_class, self.arm_b)
        self.assertEqual(
            SessionEnrollment.objects.filter(
                student=self.student, session=self.session
            ).count(),
            2,
        )
        self.assertTrue(
            PlatformEvent.objects.filter(
                action="school.student_transferred",
                target=str(self.student.pk),
            ).exists()
        )

    def test_same_class_transfer_is_rejected_without_mutation(self):
        with self.assertRaises(StudentTransferError):
            self.transfer(destination=self.arm_a)
        self.source.refresh_from_db()
        self.student.refresh_from_db()
        self.assertEqual(self.source.status, "active")
        self.assertEqual(self.student.current_class, self.arm_a)

    def test_inactive_student_cannot_transfer(self):
        for status in ("suspended", "withdrawn", "graduated"):
            self.student.status = status
            self.student.save(update_fields=["status"])
            with self.assertRaises(StudentTransferError):
                self.transfer()

    def test_missing_active_source_or_current_class_drift_fails_closed(self):
        self.source.status = "transferred"
        self.source.exited_on = date(2026, 9, 10)
        self.source.save(update_fields=["status", "exited_on"])
        with self.assertRaises(StudentTransferError):
            self.transfer()

        self.source.status = "active"
        self.source.exited_on = None
        self.source.save(update_fields=["status", "exited_on"])
        self.student.current_class = self.arm_jss2
        self.student.save(update_fields=["current_class"])
        with self.assertRaises(StudentTransferError):
            self.transfer()

    def test_foreign_destination_is_rejected(self):
        other_level = ClassLevel.objects.create(
            school=self.other, name="JSS1", order_index=1,
        )
        foreign = ClassArm.objects.create(
            school=self.other, class_level=other_level, name="A",
        )
        with self.assertRaises(StudentTransferError):
            self.transfer(destination=foreign)

    def test_invalid_transfer_dates_are_rejected(self):
        for invalid in (
            self.source.enrolled_on,
            self.source.enrolled_on.replace(day=1),
            timezone.localdate().replace(year=2027),
        ):
            with self.assertRaises(StudentTransferError):
                self.transfer(effective=invalid)

    def test_second_transfer_closes_only_current_period(self):
        self.transfer()
        second_effective = date(2026, 9, 20)
        _, second_source, final = self.transfer(
            destination=self.arm_jss2,
            effective=second_effective,
        )
        periods = list(
            SessionEnrollment.objects.filter(
                student=self.student,
                session=self.session,
            ).order_by("enrolled_on")
        )
        self.assertEqual(len(periods), 3)
        self.assertEqual(periods[0].class_arm, self.arm_a)
        self.assertEqual(periods[0].exited_on, date(2026, 9, 14))
        self.assertEqual(second_source.class_arm, self.arm_b)
        self.assertEqual(second_source.exited_on, date(2026, 9, 19))
        self.assertEqual(final.class_arm, self.arm_jss2)
        self.assertEqual(final.status, "active")
