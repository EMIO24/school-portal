from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from academics.models import AcademicSession, Term
from accounts.models import ParentStudentLink
from attendance.models import AttendanceRecord, AttendanceSession, StudentDailyPresence
from enrollment.models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile
from tenants.models import School


class Batch21PresenceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        today = timezone.localdate()
        cls.school = School.objects.create(
            name="Batch 21 School",
            slug="batch21-school",
            subdomain="batch21-school",
            subscription_plan="basic",
            arrival_cutoff_time=time(8, 0),
            student_clockout_enabled=False,
        )
        cls.other_school = School.objects.create(
            name="Other Batch 21 School",
            slug="batch21-other",
            subdomain="batch21-other",
            subscription_plan="basic",
        )
        cls.session = AcademicSession.objects.create(
            school=cls.school,
            name="2026/2027",
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=250),
            is_current=True,
        )
        cls.term = Term.objects.create(
            session=cls.session,
            name="first",
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=60),
            is_current=True,
        )
        cls.level = ClassLevel.objects.create(school=cls.school, name="JSS1", order_index=1)
        cls.arm = ClassArm.objects.create(school=cls.school, class_level=cls.level, name="A")
        cls.other_arm = ClassArm.objects.create(school=cls.school, class_level=cls.level, name="B")

        User = get_user_model()
        cls.admin = User.objects.create_user(
            email="admin@batch21.invalid", password="Pass1234!", first_name="Ada", last_name="Admin",
            role="school_admin", school=cls.school, must_change_password=False,
        )
        cls.principal = User.objects.create_user(
            email="principal@batch21.invalid", password="Pass1234!", first_name="Priya", last_name="Principal",
            role="principal", school=cls.school, must_change_password=False,
        )
        cls.class_teacher = User.objects.create_user(
            email="class@batch21.invalid", password="Pass1234!", first_name="Clara", last_name="Teacher",
            role="class_teacher", school=cls.school, must_change_password=False,
        )
        cls.teacher = User.objects.create_user(
            email="teacher@batch21.invalid", password="Pass1234!", first_name="Tom", last_name="Teacher",
            role="teacher", school=cls.school, must_change_password=False,
        )
        cls.parent = User.objects.create_user(
            email="parent@batch21.invalid", password="Pass1234!", first_name="Pat", last_name="Parent",
            role="parent", school=cls.school, must_change_password=False,
        )
        cls.student_user = User.objects.create_user(
            email="student@batch21.invalid", password="Pass1234!", first_name="Sam", last_name="Student",
            role="student", school=cls.school, must_change_password=False,
        )
        cls.other_student_user = User.objects.create_user(
            email="other-student@batch21.invalid", password="Pass1234!", first_name="Other", last_name="Student",
            role="student", school=cls.school, must_change_password=False,
        )
        cls.student = StudentProfile.objects.create(
            user=cls.student_user, school=cls.school, current_class=cls.arm, status="active",
        )
        cls.other_student = StudentProfile.objects.create(
            user=cls.other_student_user, school=cls.school, current_class=cls.other_arm, status="active",
        )
        cls.arm.class_teacher = cls.class_teacher
        cls.arm.save(update_fields=["class_teacher"])
        ParentStudentLink.objects.create(
            school=cls.school, parent=cls.parent, student=cls.student, relationship="guardian"
        )
        SessionEnrollment.objects.create(
            school=cls.school, student=cls.student, session=cls.session, class_arm=cls.arm,
            status="active", entry_reason="admission", enrolled_on=cls.session.start_date,
            created_by=cls.admin,
        )
        SessionEnrollment.objects.create(
            school=cls.school, student=cls.other_student, session=cls.session, class_arm=cls.other_arm,
            status="active", entry_reason="admission", enrolled_on=cls.session.start_date,
            created_by=cls.admin,
        )

    def client_for(self, user):
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(user).access_token))
        return client

    def aware_today(self, hour, minute):
        local = datetime.combine(timezone.localdate(), time(hour, minute))
        return timezone.make_aware(local, timezone.get_current_timezone())

    def test_principal_can_open_command_centre_and_presence(self):
        principal = self.client_for(self.principal)
        command = principal.get("/api/principal/", {"section": "snapshot"})
        self.assertEqual(command.status_code, 200)

        settings = principal.get("/api/attendance/presence/settings/")
        self.assertEqual(settings.status_code, 200)
        self.assertEqual({row["id"] for row in settings.data["classes"]}, {self.arm.pk, self.other_arm.pk})

    def test_class_teacher_presence_scope_is_only_homeroom(self):
        client = self.client_for(self.class_teacher)
        settings = client.get("/api/attendance/presence/settings/")
        self.assertEqual(settings.status_code, 200)
        self.assertEqual(settings.data["classes"], [{"id": self.arm.pk, "name": self.arm.full_name}])

        denied = client.get("/api/attendance/presence/", {"class_arm": self.other_arm.pk})
        self.assertEqual(denied.status_code, 403)

        allowed = client.get("/api/attendance/presence/", {"class_arm": self.arm.pk})
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual([row["student_id"] for row in allowed.data["students"]], [self.student.pk])

    def test_ordinary_teacher_cannot_use_gate_presence(self):
        response = self.client_for(self.teacher).get("/api/attendance/presence/settings/")
        self.assertEqual(response.status_code, 403)

    def test_clockout_is_optional_idempotent_and_requires_arrival(self):
        client = self.client_for(self.class_teacher)
        disabled = client.post("/api/attendance/presence/clock-out/", {"student": self.student.pk}, format="json")
        self.assertEqual(disabled.status_code, 403)

        self.school.student_clockout_enabled = True
        self.school.save(update_fields=["student_clockout_enabled"])
        before_arrival = client.post("/api/attendance/presence/clock-out/", {"student": self.student.pk}, format="json")
        self.assertEqual(before_arrival.status_code, 409)

        arrival = client.post("/api/attendance/presence/", {"student": self.student.pk}, format="json")
        self.assertEqual(arrival.status_code, 201)
        presence = StudentDailyPresence.objects.get(school=self.school, student=self.student, date=timezone.localdate())
        first_arrival = presence.arrival_at

        retry_arrival = client.post("/api/attendance/presence/", {"student": self.student.pk}, format="json")
        self.assertEqual(retry_arrival.status_code, 201)
        presence.refresh_from_db()
        self.assertEqual(presence.arrival_at, first_arrival)

        departure = client.post("/api/attendance/presence/clock-out/", {"student": self.student.pk}, format="json")
        self.assertEqual(departure.status_code, 200)
        presence.refresh_from_db()
        first_departure = presence.departure_at
        self.assertIsNotNone(first_departure)

        retry_departure = client.post("/api/attendance/presence/clock-out/", {"student": self.student.pk}, format="json")
        self.assertEqual(retry_departure.status_code, 200)
        presence.refresh_from_db()
        self.assertEqual(presence.departure_at, first_departure)

    def test_daily_lateness_requires_arrival_evidence_and_records_time(self):
        session = AttendanceSession.objects.create(
            school=self.school, class_arm=self.arm, teacher=self.class_teacher,
            term=self.term, date=timezone.localdate(), mode="daily",
        )
        AttendanceRecord.objects.create(
            attendance_session=session, student=self.student_user, status="present",
        )
        client = self.client_for(self.class_teacher)

        missing_time = client.patch(
            f"/api/attendance/sessions/{session.pk}/submit/",
            {"records": [{"student_id": self.student_user.pk, "status": "late", "remark": ""}]},
            format="json",
        )
        self.assertEqual(missing_time.status_code, 400)

        saved = client.patch(
            f"/api/attendance/sessions/{session.pk}/submit/",
            {"records": [{
                "student_id": self.student_user.pk, "status": "late",
                "remark": "Traffic", "arrival_time": "08:17",
            }]},
            format="json",
        )
        self.assertEqual(saved.status_code, 200)
        presence = StudentDailyPresence.objects.get(
            school=self.school, student=self.student, date=timezone.localdate()
        )
        self.assertEqual(timezone.localtime(presence.arrival_at).strftime("%H:%M"), "08:17")
        self.assertEqual(presence.class_arm_id, self.arm.pk)

    def test_parent_dashboard_shows_official_lateness_arrival_and_cautious_clockout(self):
        today = timezone.localdate()
        session = AttendanceSession.objects.create(
            school=self.school, class_arm=self.arm, teacher=self.class_teacher,
            term=self.term, date=today, mode="daily", is_finalized=True,
        )
        AttendanceRecord.objects.create(
            attendance_session=session, student=self.student_user, status="late", remark="Traffic",
        )
        StudentDailyPresence.objects.create(
            school=self.school, student=self.student, class_arm=self.arm, date=today,
            arrival_at=self.aware_today(8, 17), arrival_recorded_by=self.class_teacher,
        )
        self.school.student_clockout_enabled = True
        self.school.save(update_fields=["student_clockout_enabled"])

        response = self.client_for(self.parent).get(f"/api/parent/dashboard/{self.student.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["attendance_summary"]["late"], 1)
        self.assertEqual(response.data["presence_today"]["arrival_time"], "08:17")
        self.assertTrue(response.data["presence_today"]["late"])
        self.assertTrue(response.data["presence_today"]["clockout_enabled"])
        self.assertFalse(response.data["presence_today"]["clockout_recorded"])

    def test_historical_presence_roster_uses_enrollment_not_current_class(self):
        old_day = timezone.localdate() - timedelta(days=1)
        StudentDailyPresence.objects.create(
            school=self.school,
            student=self.student,
            class_arm=self.arm,
            date=old_day,
            arrival_at=timezone.make_aware(
                datetime.combine(old_day, time(7, 50)),
                timezone.get_current_timezone(),
            ),
            arrival_recorded_by=self.admin,
        )
        self.student.current_class = self.other_arm
        self.student.save(update_fields=["current_class"])

        response = self.client_for(self.admin).get(
            "/api/attendance/presence/",
            {"class_arm": self.arm.pk, "date": old_day.isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [row["student_id"] for row in response.data["students"]],
            [self.student.pk],
        )
        self.assertEqual(
            response.data["students"][0]["presence"]["class_arm"],
            self.arm.full_name,
        )

    def test_parent_cannot_open_unlinked_child_dashboard(self):
        response = self.client_for(self.parent).get(f"/api/parent/dashboard/{self.other_student.pk}/")
        self.assertEqual(response.status_code, 403)

    def test_only_school_admin_can_change_presence_configuration(self):
        principal = self.client_for(self.principal)
        denied = principal.patch(
            "/api/attendance/presence/settings/",
            {"arrival_cutoff_time": "07:45", "student_clockout_enabled": True},
            format="json",
        )
        self.assertEqual(denied.status_code, 403)

        admin = self.client_for(self.admin)
        changed = admin.patch(
            "/api/attendance/presence/settings/",
            {"arrival_cutoff_time": "07:45", "student_clockout_enabled": True},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        self.school.refresh_from_db()
        self.assertEqual(self.school.arrival_cutoff_time, time(7, 45))
        self.assertTrue(self.school.student_clockout_enabled)
