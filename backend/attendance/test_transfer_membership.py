from datetime import date
from types import SimpleNamespace

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import CustomUser
from academics.models import AcademicSession, Term
from enrollment.models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile
from enrollment.transfers import transfer_student
from tenants.models import School

from .models import AttendanceRecord, StudentDailyPresence
from .serializers import AttendanceSessionCreateSerializer
from .views import AttendanceSessionViewSet


class TransferAwareAttendanceTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Transfer Attendance School",
            slug="transfer-attendance",
            subdomain="transfer-attendance",
        )
        self.admin = CustomUser.objects.create_user(
            "admin@transfer-attendance.test",
            "Password!123",
            school=self.school,
            role="school_admin",
        )
        self.user = CustomUser.objects.create_user(
            "student@transfer-attendance.test",
            "Password!123",
            school=self.school,
            role="student",
        )
        self.level = ClassLevel.objects.create(
            school=self.school, name="JSS1", order_index=1,
        )
        self.old_arm = ClassArm.objects.create(
            school=self.school, class_level=self.level, name="A",
        )
        self.new_arm = ClassArm.objects.create(
            school=self.school, class_level=self.level, name="B",
        )
        self.session = AcademicSession.objects.create(
            school=self.school,
            name="2026/27",
            start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31),
            is_current=True,
        )
        self.term = Term.objects.create(
            session=self.session,
            name="first",
            start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 18),
            is_current=True,
        )
        self.student = StudentProfile.objects.create(
            school=self.school,
            user=self.user,
            current_class=self.old_arm,
            admission_number="ATTTRN001",
        )
        SessionEnrollment.objects.create(
            school=self.school,
            student=self.student,
            session=self.session,
            class_arm=self.old_arm,
            status="active",
            entry_reason="admission",
            enrolled_on=date(2026, 9, 1),
            created_by=self.admin,
        )
        transfer_student(
            school=self.school,
            student=self.student,
            destination_class=self.new_arm,
            effective_date=date(2026, 9, 15),
            actor=self.admin,
            reason="Class balancing",
        )
        self.request_context = SimpleNamespace(
            tenant=self.school,
            user=self.admin,
        )
        self.factory = APIRequestFactory()

    def create_register(self, arm, on_date):
        serializer = AttendanceSessionCreateSerializer(
            data={
                "class_arm": arm.pk,
                "term": self.term.pk,
                "date": str(on_date),
                "mode": "daily",
            },
            context={"request": self.request_context},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        return serializer.save()

    def test_old_class_register_before_transfer_keeps_student(self):
        register = self.create_register(self.old_arm, date(2026, 9, 14))
        self.assertTrue(
            AttendanceRecord.objects.filter(
                attendance_session=register,
                student=self.user,
            ).exists()
        )

    def test_old_class_register_after_transfer_excludes_student(self):
        register = self.create_register(self.old_arm, date(2026, 9, 15))
        self.assertFalse(
            AttendanceRecord.objects.filter(
                attendance_session=register,
                student=self.user,
            ).exists()
        )

    def test_new_class_register_from_transfer_date_includes_student(self):
        register = self.create_register(self.new_arm, date(2026, 9, 15))
        self.assertTrue(
            AttendanceRecord.objects.filter(
                attendance_session=register,
                student=self.user,
            ).exists()
        )

    def test_backdated_old_class_attendance_remains_editable_after_transfer(self):
        register = self.create_register(self.old_arm, date(2026, 9, 14))
        request = self.factory.patch(
            f"/api/attendance/sessions/{register.pk}/submit/",
            {
                "records": [{
                    "student_id": self.user.pk,
                    "status": "late",
                    "remark": "Backdated correction",
                    "arrival_time": "08:15",
                }]
            },
            format="json",
        )
        request.tenant = self.school
        force_authenticate(request, self.admin)

        response = AttendanceSessionViewSet.as_view(
            {"patch": "submit"},
            permission_classes=[],
        )(request, pk=register.pk)
        self.assertEqual(response.status_code, 200)
        record = AttendanceRecord.objects.get(
            attendance_session=register,
            student=self.user,
        )
        self.assertEqual(record.status, "late")
        presence = StudentDailyPresence.objects.get(
            school=self.school, student=self.student, date=register.date,
        )
        self.assertEqual(presence.class_arm_id, self.old_arm.pk)
        self.assertEqual(presence.arrival_at.date(), register.date)

    def test_old_class_register_after_transfer_rejects_student_submission(self):
        register = self.create_register(self.old_arm, date(2026, 9, 16))
        request = self.factory.patch(
            f"/api/attendance/sessions/{register.pk}/submit/",
            {
                "records": [{
                    "student_id": self.user.pk,
                    "status": "present",
                    "remark": "",
                }]
            },
            format="json",
        )
        request.tenant = self.school
        force_authenticate(request, self.admin)

        response = AttendanceSessionViewSet.as_view(
            {"patch": "submit"},
            permission_classes=[],
        )(request, pk=register.pk)
        self.assertEqual(response.status_code, 400)
        self.assertIn("must belong to this class", str(response.data))

    def test_finalize_uses_historical_roster_for_register_date(self):
        register = self.create_register(self.old_arm, date(2026, 9, 14))
        request = self.factory.patch(
            f"/api/attendance/sessions/{register.pk}/finalize/",
            {},
            format="json",
        )
        request.tenant = self.school
        force_authenticate(request, self.admin)

        response = AttendanceSessionViewSet.as_view(
            {"patch": "finalize"},
            permission_classes=[],
        )(request, pk=register.pk)
        self.assertEqual(response.status_code, 200)
