from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from enrollment.models import ClassArm, ClassLevel, SessionEnrollment, StudentProfile
from promotion.models import PromotionRecord
from tenants.models import School

from .models import AcademicRollover, AcademicSession, Term


class AcademicRolloverPreviewTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(
            name="Preview School", slug="preview-school", subdomain="preview-school"
        )
        self.other = School.objects.create(
            name="Other Preview School",
            slug="other-preview-school",
            subdomain="other-preview-school",
        )
        self.admin = CustomUser.objects.create_user(
            "admin@preview.test",
            "Password!123",
            school=self.school,
            role="school_admin",
        )
        self.teacher = CustomUser.objects.create_user(
            "teacher@preview.test",
            "Password!123",
            school=self.school,
            role="teacher",
        )
        self.student_user = CustomUser.objects.create_user(
            "student@preview.test",
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
        self.source_first = Term.objects.create(
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
        self.destination_first = Term.objects.create(
            session=self.destination,
            name="first",
            start_date=date(2027, 9, 1),
            end_date=date(2027, 12, 17),
        )
        self.enrollment = SessionEnrollment.objects.create(
            school=self.school,
            student=self.student,
            session=self.source,
            class_arm=self.arm1,
            status="active",
            entry_reason="admission",
            enrolled_on=date(2026, 10, 1),
            created_by=self.admin,
        )

        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def preview(self, destination=None):
        destination = destination or self.destination
        return self.client.post(
            f"/api/sessions/{self.source.pk}/rollover-preview/",
            {"destination_session_id": destination.pk},
            format="json",
        )

    def test_missing_decision_is_a_blocker_and_preview_is_persisted_without_student_mutation(self):
        response = self.preview()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["ready"])
        self.assertEqual(response.data["status"], "preparing")
        self.assertEqual(response.data["summary"]["source_students"], 1)
        self.assertEqual(response.data["summary"]["decision_required"], 1)
        self.assertEqual(response.data["summary"]["unresolved"], 1)
        self.assertIn(
            "MISSING_PROMOTION_DECISION",
            {row["code"] for row in response.data["blockers"]},
        )

        rollover = AcademicRollover.objects.get(
            school=self.school,
            source_session=self.source,
            destination_session=self.destination,
        )
        self.assertEqual(rollover.status, "preparing")
        self.assertEqual(rollover.student_count, 1)
        self.assertEqual(
            rollover.preview_snapshot["summary"]["unresolved"], 1
        )

        self.student.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.student.current_class_id, self.arm1.pk)
        self.assertEqual(self.enrollment.status, "active")
        self.assertFalse(
            SessionEnrollment.objects.filter(
                student=self.student,
                session=self.destination,
            ).exists()
        )

    def test_complete_valid_decision_set_marks_preview_ready_and_counts_decisions(self):
        PromotionRecord.objects.create(
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

        response = self.preview()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["ready"], response.data)
        self.assertEqual(response.data["status"], "ready")
        self.assertEqual(response.data["blockers"], [])
        self.assertEqual(response.data["summary"]["decided"], 1)
        self.assertEqual(response.data["summary"]["promoted"], 1)
        self.assertEqual(response.data["summary"]["unresolved"], 0)
        self.assertEqual(response.data["students"][0]["decision"], "promoted")
        self.assertTrue(response.data["students"][0]["ready"])

        rollover = AcademicRollover.objects.get(
            school=self.school,
            source_session=self.source,
            destination_session=self.destination,
        )
        self.assertEqual(rollover.status, "ready")
        self.assertEqual(rollover.promoted_count, 1)

        # 19E2 is preview-only. Existing placement and current pointers are untouched.
        self.student.refresh_from_db()
        self.enrollment.refresh_from_db()
        self.assertEqual(self.student.current_class_id, self.arm1.pk)
        self.assertEqual(self.enrollment.status, "active")
        self.assertFalse(self.destination.is_current)

    def test_invalid_promotion_destination_class_is_reported_not_applied(self):
        PromotionRecord.objects.create(
            school=self.school,
            student=self.student,
            from_session=self.source,
            to_session=self.destination,
            from_class=self.arm1,
            to_class=self.arm1,
            decision="promoted",
            criteria_met=True,
            decided_by=self.admin,
        )

        response = self.preview()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["ready"])
        self.assertIn(
            "PROMOTION_CLASS_NOT_HIGHER",
            {row["code"] for row in response.data["blockers"]},
        )
        self.assertIn(
            "PROMOTION_CLASS_NOT_HIGHER",
            {row["code"] for row in response.data["students"][0]["issues"]},
        )

    def test_destination_first_term_is_a_hard_blocker(self):
        self.destination_first.delete()
        PromotionRecord.objects.create(
            school=self.school,
            student=self.student,
            from_session=self.source,
            to_session=self.destination,
            from_class=self.arm1,
            to_class=self.arm2,
            decision="promoted",
            decided_by=self.admin,
        )

        response = self.preview()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["ready"])
        self.assertIn(
            "DESTINATION_FIRST_TERM_MISSING",
            {row["code"] for row in response.data["blockers"]},
        )

    def test_cross_tenant_destination_is_rejected(self):
        other_destination = AcademicSession.objects.create(
            school=self.other,
            name="2027/28",
            start_date=date(2027, 9, 1),
            end_date=date(2028, 7, 31),
        )
        response = self.preview(other_destination)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(
            AcademicRollover.objects.filter(school=self.school).exists()
        )

    def test_teacher_cannot_prepare_rollover_preview(self):
        self.client.force_authenticate(self.teacher)
        response = self.preview()
        self.assertEqual(response.status_code, 403)

    def test_lifecycle_closed_student_does_not_require_duplicate_year_end_decision(self):
        self.student.status = "withdrawn"
        self.student.current_class = None
        self.student.save(update_fields=["status", "current_class"])
        self.student_user.is_active = False
        self.student_user.save(update_fields=["is_active"])
        self.enrollment.status = "withdrawn"
        self.enrollment.exited_on = date(2027, 5, 1)
        self.enrollment.save(update_fields=["status", "exited_on", "updated_at"])

        response = self.preview()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["ready"], response.data)
        self.assertEqual(response.data["summary"]["decision_required"], 0)
        self.assertEqual(response.data["summary"]["lifecycle_exempt"], 1)
        self.assertTrue(response.data["students"][0]["lifecycle_exempt"])


    def test_current_class_drift_blocks_preview_and_is_persisted(self):
        PromotionRecord.objects.create(
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
        drift_arm = ClassArm.objects.create(
            school=self.school,
            class_level=self.level1,
            name="B",
        )
        self.student.current_class = drift_arm
        self.student.save(update_fields=["current_class"])

        response = self.preview()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["ready"])
        self.assertIn(
            "CURRENT_CLASS_DRIFT",
            {row["code"] for row in response.data["blockers"]},
        )
        self.assertIn(
            "CURRENT_CLASS_DRIFT",
            {row["code"] for row in response.data["students"][0]["issues"]},
        )

    def test_preview_persists_complete_carry_forward_policy_and_fingerprint(self):
        response = self.preview()
        self.assertEqual(response.status_code, 200, response.data)
        policy = response.data["carry_forward_policy"]
        self.assertIn("staff_profiles", policy["reuse"])
        self.assertIn("fee_categories", policy["reuse"])
        self.assertIn("promotion_criteria", policy["reuse"])
        self.assertIn("assessment_modes", policy["review_or_create"])
        self.assertIn("ledger_history", policy["never_copy"])
        self.assertEqual(len(response.data["snapshot_fingerprint"]), 64)

        rollover = AcademicRollover.objects.get(
            school=self.school,
            source_session=self.source,
            destination_session=self.destination,
        )
        self.assertEqual(
            rollover.configuration_options["snapshot_fingerprint"],
            response.data["snapshot_fingerprint"],
        )
        self.assertEqual(
            rollover.configuration_options["carry_forward_policy"],
            policy,
        )
