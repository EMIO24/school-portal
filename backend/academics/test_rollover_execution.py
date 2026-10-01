from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from enrollment.models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile
from promotion.models import PromotionRecord
from tenants.models import PlatformEvent, School

from .models import AcademicRollover, AcademicSession, Term
from .rollover import prepare_rollover_preview


class AcademicRolloverExecutionTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Execution School",
            slug="execution-school",
            subdomain="execution-school",
        )
        self.admin = CustomUser.objects.create_user(
            "admin@execution.test",
            "Password!123",
            school=self.school,
            role="school_admin",
        )
        self.teacher = CustomUser.objects.create_user(
            "teacher@execution.test",
            "Password!123",
            school=self.school,
            role="teacher",
        )
        self.student_user = CustomUser.objects.create_user(
            "student@execution.test",
            "Password!123",
            school=self.school,
            role="student",
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
        self.arm1b = ClassArm.objects.create(
            school=self.school, class_level=self.level1, name="B"
        )

        self.student = StudentProfile.objects.create(
            school=self.school,
            user=self.student_user,
            current_class=self.arm1,
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
        self.source_enrollment = SessionEnrollment.objects.create(
            school=self.school,
            student=self.student,
            session=self.source,
            class_arm=self.arm1,
            status="active",
            entry_reason="admission",
            enrolled_on=self.source.start_date,
            created_by=self.admin,
        )

        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def create_promoted_decision(self):
        return PromotionRecord.objects.create(
            school=self.school,
            student=self.student,
            from_session=self.source,
            to_session=self.destination,
            from_class=self.arm1,
            to_class=self.arm2,
            decision="promoted",
            criteria_met=True,
            decided_by=self.admin,
        )

    def execute(self, key="rollover-2027"):
        return self.client.post(
            f"/api/sessions/{self.source.pk}/rollover-execute/",
            {
                "destination_session_id": self.destination.pk,
                "idempotency_key": key,
            },
            format="json",
        )

    def test_ready_rollover_executes_entire_cutover_atomically(self):
        decision = self.create_promoted_decision()
        preview = prepare_rollover_preview(
            school=self.school,
            source_session=self.source,
            destination_session=self.destination,
            actor=self.admin,
        )
        self.assertTrue(preview["ready"], preview)

        response = self.execute()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "completed")
        self.assertFalse(response.data["idempotent_replay"])
        self.assertEqual(response.data["summary"]["promoted"], 1)

        self.source.refresh_from_db()
        self.destination.refresh_from_db()
        self.source_term.refresh_from_db()
        self.destination_term.refresh_from_db()
        self.source_enrollment.refresh_from_db()
        self.student.refresh_from_db()
        self.student_user.refresh_from_db()

        destination_enrollment = SessionEnrollment.objects.get(
            school=self.school,
            student=self.student,
            session=self.destination,
        )
        rollover = AcademicRollover.objects.get(
            school=self.school,
            source_session=self.source,
            destination_session=self.destination,
        )

        self.assertFalse(self.source.is_current)
        self.assertTrue(self.destination.is_current)
        self.assertFalse(self.source_term.is_current)
        self.assertTrue(self.destination_term.is_current)
        self.assertEqual(self.source_enrollment.status, "completed")
        self.assertEqual(self.source_enrollment.exited_on, self.source.end_date)
        self.assertEqual(destination_enrollment.class_arm, self.arm2)
        self.assertEqual(destination_enrollment.entry_reason, "promotion")
        self.assertEqual(destination_enrollment.enrolled_on, self.destination.start_date)
        self.assertEqual(self.student.current_class, self.arm2)
        self.assertEqual(self.student.status, "active")
        self.assertTrue(self.student_user.is_active)
        self.assertEqual(rollover.status, "completed")
        self.assertEqual(rollover.completed_by, self.admin)
        self.assertIsNotNone(rollover.completed_at)
        self.assertEqual(rollover.promoted_count, 1)
        self.assertEqual(rollover.idempotency_key, "rollover-2027")
        self.assertTrue(
            PlatformEvent.objects.filter(
                action="school.academic_rollover",
                target=str(rollover.pk),
                details__source_session_id=self.source.pk,
                details__destination_session_id=self.destination.pk,
            ).exists()
        )
        self.assertEqual(decision.to_class, self.arm2)

    def test_completed_rollover_replay_is_idempotent(self):
        self.create_promoted_decision()
        first = self.execute()
        self.assertEqual(first.status_code, 200, first.data)

        destination_enrollment_id = SessionEnrollment.objects.get(
            student=self.student,
            session=self.destination,
        ).pk
        event_count = PlatformEvent.objects.filter(
            action="school.academic_rollover"
        ).count()

        second = self.execute(key="different-retry-key")
        self.assertEqual(second.status_code, 200, second.data)
        self.assertTrue(second.data["idempotent_replay"])
        self.assertEqual(
            SessionEnrollment.objects.filter(
                student=self.student,
                session=self.destination,
            ).count(),
            1,
        )
        self.assertEqual(
            SessionEnrollment.objects.get(
                student=self.student,
                session=self.destination,
            ).pk,
            destination_enrollment_id,
        )
        self.assertEqual(
            PlatformEvent.objects.filter(
                action="school.academic_rollover"
            ).count(),
            event_count,
        )

    def test_not_ready_rollover_is_rejected_without_state_change(self):
        response = self.execute()
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("year-end", str(response.data).lower())

        self.source.refresh_from_db()
        self.destination.refresh_from_db()
        self.source_enrollment.refresh_from_db()
        self.student.refresh_from_db()

        self.assertTrue(self.source.is_current)
        self.assertFalse(self.destination.is_current)
        self.assertEqual(self.source_enrollment.status, "active")
        self.assertEqual(self.student.current_class, self.arm1)
        self.assertFalse(
            SessionEnrollment.objects.filter(
                student=self.student,
                session=self.destination,
            ).exists()
        )

    def test_state_drift_during_execution_rolls_back_everything(self):
        self.create_promoted_decision()
        preview = prepare_rollover_preview(
            school=self.school,
            source_session=self.source,
            destination_session=self.destination,
            actor=self.admin,
        )
        self.assertTrue(preview["ready"])

        # Simulate an out-of-band pointer change after preview. The fresh readiness
        # check still sees valid historical placement, but the executor must fail closed.
        self.student.current_class = self.arm1b
        self.student.save(update_fields=["current_class"])

        response = self.execute()
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("current class changed", str(response.data).lower())

        self.source.refresh_from_db()
        self.destination.refresh_from_db()
        self.source_enrollment.refresh_from_db()
        self.student.refresh_from_db()
        rollover = AcademicRollover.objects.get(
            school=self.school,
            source_session=self.source,
            destination_session=self.destination,
        )

        self.assertTrue(self.source.is_current)
        self.assertFalse(self.destination.is_current)
        self.assertEqual(self.source_enrollment.status, "active")
        self.assertEqual(self.student.current_class, self.arm1b)
        self.assertEqual(rollover.status, "ready")
        self.assertIsNone(rollover.completed_at)
        self.assertFalse(
            SessionEnrollment.objects.filter(
                student=self.student,
                session=self.destination,
            ).exists()
        )
        self.assertFalse(
            PlatformEvent.objects.filter(action="school.academic_rollover").exists()
        )

    def test_matching_legacy_applied_decision_can_finish_calendar_cutover(self):
        record = self.create_promoted_decision()
        self.source_enrollment.status = "completed"
        self.source_enrollment.exited_on = self.source.end_date
        self.source_enrollment.save(
            update_fields=["status", "exited_on", "updated_at"]
        )
        SessionEnrollment.objects.create(
            school=self.school,
            student=self.student,
            session=self.destination,
            class_arm=self.arm2,
            status="active",
            entry_reason="promotion",
            enrolled_on=self.destination.start_date,
            notes=f"Created by promotion decision {record.pk}.",
            created_by=self.admin,
        )
        self.student.current_class = self.arm2
        self.student.save(update_fields=["current_class"])

        response = self.execute()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(
            SessionEnrollment.objects.filter(
                student=self.student,
                session=self.destination,
            ).count(),
            1,
        )
        self.destination.refresh_from_db()
        self.assertTrue(self.destination.is_current)

    def test_graduation_and_withdrawal_are_applied_without_destination_enrollments(self):
        final_level = ClassLevel.objects.create(
            school=self.school, name="SS3", order_index=6, is_final_year=True
        )
        final_arm = ClassArm.objects.create(
            school=self.school, class_level=final_level, name="A"
        )
        graduate_user = CustomUser.objects.create_user(
            "graduate@execution.test",
            "Password!123",
            school=self.school,
            role="student",
        )
        graduate = StudentProfile.objects.create(
            school=self.school,
            user=graduate_user,
            current_class=final_arm,
        )
        graduate_enrollment = SessionEnrollment.objects.create(
            school=self.school,
            student=graduate,
            session=self.source,
            class_arm=final_arm,
            status="active",
            entry_reason="manual",
            enrolled_on=self.source.start_date,
            created_by=self.admin,
        )

        PromotionRecord.objects.create(
            school=self.school,
            student=self.student,
            from_session=self.source,
            from_class=self.arm1,
            decision="withdrawn",
            criteria_met=False,
            decided_by=self.admin,
        )
        PromotionRecord.objects.create(
            school=self.school,
            student=graduate,
            from_session=self.source,
            from_class=final_arm,
            decision="graduated",
            criteria_met=True,
            decided_by=self.admin,
        )

        response = self.execute()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["summary"]["withdrawn"], 1)
        self.assertEqual(response.data["summary"]["graduated"], 1)

        self.student.refresh_from_db()
        self.student_user.refresh_from_db()
        self.source_enrollment.refresh_from_db()
        graduate.refresh_from_db()
        graduate_user.refresh_from_db()
        graduate_enrollment.refresh_from_db()

        self.assertEqual(self.student.status, "withdrawn")
        self.assertIsNone(self.student.current_class)
        self.assertFalse(self.student_user.is_active)
        self.assertEqual(self.source_enrollment.status, "withdrawn")

        self.assertEqual(graduate.status, "graduated")
        self.assertIsNone(graduate.current_class)
        self.assertFalse(graduate_user.is_active)
        self.assertEqual(graduate_enrollment.status, "graduated")

        self.assertFalse(
            SessionEnrollment.objects.filter(
                session=self.destination,
                student__in=[self.student, graduate],
            ).exists()
        )

    def test_teacher_cannot_execute_rollover(self):
        self.create_promoted_decision()
        self.client.force_authenticate(self.teacher)
        response = self.execute()
        self.assertEqual(response.status_code, 403)


    def test_rollover_history_is_admin_only_and_reports_completion_metadata(self):
        self.create_promoted_decision()
        executed = self.execute()
        self.assertEqual(executed.status_code, 200, executed.data)

        history = self.client.get("/api/sessions/rollover-history/")
        self.assertEqual(history.status_code, 200, history.data)
        self.assertEqual(len(history.data), 1)
        row = history.data[0]
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["source_session"]["id"], self.source.pk)
        self.assertEqual(row["destination_session"]["id"], self.destination.pk)
        self.assertEqual(row["promoted_count"], 1)
        self.assertEqual(row["completed_by"], self.admin.email)
        self.assertEqual(len(row["snapshot_fingerprint"]), 64)

        self.client.force_authenticate(self.teacher)
        denied = self.client.get("/api/sessions/rollover-history/")
        self.assertEqual(denied.status_code, 403)
