"""Recovery preserves identities and committed institutional history."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from academics import test_rollover_execution as rollover_fixtures
from academics.rollover import execute_rollover, RolloverSafetyError
from academics.models import AcademicRollover, AcademicSession, Term
from tenants.models import PlatformEvent
from tenants import test_batch26c_campus_history as campus_fixtures
from promotion import tests as promotion_fixtures
from promotion.models import PromotionRecord
from .models import StudentProfile, SessionEnrollment, StudentRecordEntry, StaffProfile, SubjectAssignment, MigrationRowRecord, Subject
from .session_enrollment import ensure_current_enrollment, EnrollmentPlacementError
from . import test_migration as import_fixtures
from . import migration_import
from gradebook import test_academic_workflow as result_fixtures
from gradebook.models import ScoreEntry
from attendance import test_presence as presence_fixtures
from attendance.models import StudentDailyPresence
from fees.models import FeeCategory, FeeSchedule, StudentLedgerEntry
from django.core.files.uploadedfile import SimpleUploadedFile


def concurrent(test, operation):
    barrier = Barrier(2)
    def worker():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '15s'")
            barrier.wait(timeout=10)
            return operation()
        finally:
            connection.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker) for _ in range(2)]
        return [future.result(timeout=30) for future in futures]


class AdmissionRecoveryTests(TransactionTestCase):
    setUp = campus_fixtures.Batch26CCampusTests.setUp
    client_for = campus_fixtures.Batch26CCampusTests.client_for

    def admit(self):
        return self.client_for().post(f"/api/operations/admissions/{self.application.pk}/decision/",
                                     {"decision": "admit", "class_arm": self.arm.pk}, format="json")

    def assert_one_admission(self):
        self.application.refresh_from_db()
        student = self.application.admitted_student
        self.assertIsNotNone(student)
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(), 2)
        self.assertEqual(SessionEnrollment.objects.filter(student=student).count(), 1)
        self.assertEqual(StudentRecordEntry.objects.filter(student=student, kind="enrollment").count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action="admissions.student_admitted").count(), 1)
        return student.admission_number

    def test_sequential_and_network_replay_keep_one_identity(self):
        self.assertEqual(self.admit().status_code, 201)
        number = self.assert_one_admission()
        for _ in range(2):
            self.assertEqual(self.admit().status_code, 200)
            self.assertEqual(self.assert_one_admission(), number)

    def test_concurrent_admission_keeps_one_history(self):
        self.assertEqual(sorted(r.status_code for r in concurrent(self, self.admit)), [200, 201])
        self.assert_one_admission()

    def test_completed_admission_without_companion_history_fails_closed(self):
        self.assertEqual(self.admit().status_code, 201)
        self.application.refresh_from_db()
        StudentRecordEntry.objects.filter(student=self.application.admitted_student).delete()
        self.assertEqual(self.admit().status_code, 409)
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(), 2)
        self.assertFalse(StudentRecordEntry.objects.filter(student=self.application.admitted_student).exists())

    def test_completed_admission_without_enrollment_fails_closed(self):
        self.assertEqual(self.admit().status_code, 201)
        self.application.refresh_from_db()
        SessionEnrollment.objects.filter(student=self.application.admitted_student).delete()
        self.assertEqual(self.admit().status_code, 409)
        self.assertFalse(SessionEnrollment.objects.filter(student=self.application.admitted_student).exists())

    def test_stale_current_session_does_not_create_placement(self):
        SessionEnrollment.objects.filter(student=self.student).delete()
        AcademicSession.objects.filter(pk=self.session.pk).update(is_current=False)
        with self.assertRaises(EnrollmentPlacementError):
            ensure_current_enrollment(school=self.school, student=self.student, class_arm=self.arm,
                                      actor=self.admin, current_session=self.session)
        self.assertFalse(SessionEnrollment.objects.filter(student=self.student).exists())

    def test_interrupted_admission_rolls_back_identity_and_can_retry(self):
        with patch("enrollment.operations.StudentRecordEntry.objects.create", side_effect=RuntimeError("record interrupted")):
            with self.assertRaisesRegex(RuntimeError, "record interrupted"):
                self.admit()
        self.application.refresh_from_db()
        self.assertIsNone(self.application.admitted_student_id)
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(), 1)
        self.assertEqual(self.admit().status_code, 201)
        self.assert_one_admission()

    def test_legacy_student_csv_retry_after_class_change_fails_closed(self):
        body = "first_name,last_name,gender,dob,class_level,class_arm,campus,guardian_name,guardian_phone\nRetry,Legacy,male,2013-01-02,JSS1,A,ORIGINAL,Guardian,08011111111"
        def upload():
            return self.client_for().post("/api/students/bulk-import/", {
                "file": SimpleUploadedFile("students.csv", body.encode(), content_type="text/csv")}, format="multipart")
        first = upload()
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["success_count"], 1, first.data)
        profile = StudentProfile.objects.get(user__first_name="Retry")
        profile.current_class = None
        profile.save(update_fields=["current_class"])
        retry = upload()
        self.assertEqual(retry.data["success_count"], 0, retry.data)
        self.assertEqual(retry.data["error_count"], 1)
        self.assertEqual(StudentProfile.objects.filter(user__first_name="Retry").count(), 1)

    def test_failed_no_arm_import_rolls_back_default_class_and_student(self):
        self.school.uses_class_arms = False
        self.school.save(update_fields=["uses_class_arms"])
        AcademicSession.objects.filter(pk=self.session.pk).update(is_current=False)
        body = "first_name,last_name,gender,dob,class_level,campus,guardian_name,guardian_phone\nRetry,NoSession,male,2013-01-02,JSS1,ORIGINAL,Guardian,08011111111"
        response = self.client_for().post("/api/students/bulk-import/", {
            "file": SimpleUploadedFile("students.csv", body.encode(), content_type="text/csv")}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["success_count"], 0)
        self.assertEqual(response.data["error_count"], 1)
        self.assertFalse(StudentProfile.objects.filter(user__first_name="Retry").exists())
        self.assertFalse(self.school.class_arms.filter(is_default=True).exists())


class PromotionRecoveryTests(TransactionTestCase):
    setUp = promotion_fixtures.PromotionEnrollmentHistoryTests.setUp
    execute = promotion_fixtures.PromotionEnrollmentHistoryTests.execute
    promoted_body = promotion_fixtures.PromotionEnrollmentHistoryTests.promoted_body

    def assert_staged_once(self):
        self.assertEqual(PromotionRecord.objects.filter(student=self.student).count(), 1)
        self.assertEqual(SessionEnrollment.objects.filter(student=self.student).count(), 1)
        self.student.refresh_from_db()
        self.source_enrollment.refresh_from_db()
        self.assertEqual(self.student.current_class_id, self.arm1.pk)
        self.assertEqual(self.source_enrollment.status, "active")

    def test_promotion_retry_preserves_source_history(self):
        for _ in range(3):
            response = self.execute(self.promoted_body())
            self.assertEqual(response.status_code, 200, response.data)
        self.assert_staged_once()

    def test_concurrent_promotion_stages_one_decision(self):
        responses = concurrent(self, lambda: self.execute(self.promoted_body()))
        self.assertEqual([r.status_code for r in responses], [200, 200])
        self.assert_staged_once()


class RolloverRecoveryTests(TransactionTestCase):
    create_promoted_decision = rollover_fixtures.AcademicRolloverExecutionTests.create_promoted_decision

    def setUp(self):
        rollover_fixtures.AcademicRolloverExecutionTests.setUp(self)
        category = FeeCategory.objects.create(school=self.school, name="Historical tuition")
        schedule = FeeSchedule.objects.create(school=self.school, term=self.source_term,
            class_level=self.level1, fee_category=category, amount="50000")
        StudentLedgerEntry.objects.create(school=self.school, student=self.student, term=self.source_term,
            fee_schedule=schedule, kind="charge", signed_amount="50000", description="Recorded obligation",
            effective_date=self.source.start_date)
        subject = Subject.objects.create(school=self.school, name="History", code="HIST")
        ScoreEntry.objects.create(school=self.school, student=self.student_user, class_arm=self.arm1,
            subject=subject, session=self.source, term=self.source_term, teacher=self.teacher,
            exam_score=60, is_published=True, review_state="approved")
        self.original_finance = list(StudentLedgerEntry.objects.values())
        self.original_scores = list(ScoreEntry.objects.values())

    def rollover(self):
        return execute_rollover(school=self.school, source_session=self.source,
                                destination_session=self.destination, actor=self.admin,
                                idempotency_key="26d-recovery")

    def assert_cutover_once(self):
        self.assertEqual(AcademicRollover.objects.filter(status="completed").count(), 1)
        self.assertEqual(SessionEnrollment.objects.filter(student=self.student).count(), 2)
        self.assertEqual(PlatformEvent.objects.filter(action="school.academic_rollover").count(), 1)
        self.source_enrollment.refresh_from_db()
        self.assertEqual(self.source_enrollment.status, "completed")
        self.assertEqual(self.source_enrollment.exited_on, self.source.end_date)
        self.assertEqual(AcademicSession.objects.filter(school=self.school, is_current=True).get().pk, self.destination.pk)
        self.assertEqual(list(StudentLedgerEntry.objects.values()), self.original_finance)
        self.assertEqual(list(ScoreEntry.objects.values()), self.original_scores)
        self.assertEqual(FeeSchedule.objects.count(), 1)

    def test_rollover_replay_preserves_history(self):
        self.create_promoted_decision()
        first = self.rollover()
        replay = self.rollover()
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])
        self.assertEqual(first["summary"], replay["summary"])
        self.assert_cutover_once()

    def test_failure_after_placement_rolls_back_then_retry_succeeds(self):
        self.create_promoted_decision()
        with patch("tenants.models.PlatformEvent.objects.create", side_effect=RuntimeError("audit interrupted")):
            with self.assertRaisesRegex(RuntimeError, "audit interrupted"):
                self.rollover()
        self.source_enrollment.refresh_from_db()
        self.assertEqual(self.source_enrollment.status, "active")
        self.assertEqual(SessionEnrollment.objects.filter(student=self.student).count(), 1)
        self.assertTrue(AcademicSession.objects.get(pk=self.source.pk).is_current)
        self.rollover()
        self.assert_cutover_once()

    def test_concurrent_rollover_commits_one_cutover(self):
        self.create_promoted_decision()
        results = concurrent(self, self.rollover)
        self.assertEqual(sorted(r["idempotent_replay"] for r in results), [False, True])
        self.assert_cutover_once()

    def test_completed_rollover_missing_destination_history_fails_closed(self):
        self.create_promoted_decision()
        self.rollover()
        SessionEnrollment.objects.filter(student=self.student, session=self.destination).delete()
        with self.assertRaises(RolloverSafetyError):
            self.rollover()
        self.assertFalse(SessionEnrollment.objects.filter(session=self.destination).exists())

    def test_stale_rollover_key_cannot_target_another_session_pair(self):
        self.create_promoted_decision()
        self.rollover()
        later = AcademicSession.objects.create(school=self.school, name="2028/29", start_date="2028-09-01", end_date="2029-07-31")
        with self.assertRaises(RolloverSafetyError):
            execute_rollover(school=self.school, source_session=self.destination, destination_session=later,
                             actor=self.admin, idempotency_key="26d-recovery")
        self.assert_cutover_once()

    def test_completed_rollover_missing_decision_fails_closed(self):
        self.create_promoted_decision()
        self.rollover()
        PromotionRecord.objects.filter(student=self.student).delete()
        with self.assertRaises(RolloverSafetyError):
            self.rollover()
        self.assertFalse(PromotionRecord.objects.filter(student=self.student).exists())


class ImportRecoveryTests(TestCase):
    setUp = import_fixtures.MigrationCentreTests.setUp
    upload = import_fixtures.MigrationCentreTests.upload

    def interrupted_import(self, domain, body):
        original = migration_import.create
        calls = []
        def interrupted(*args):
            result = original(*args)
            calls.append(args[1])
            if len(calls) == 2:
                raise RuntimeError("connection lost after row writes")
            return result
        with patch("enrollment.migration_import.create", side_effect=interrupted):
            response = self.upload(domain, "import", body)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["counts"]["CREATE"], 1)
        self.assertEqual(response.data["counts"]["REJECT"], 1)
        original_history = list(MigrationRowRecord.objects.order_by("pk").values())
        retry = self.upload(domain, "import", body)
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(retry.data["counts"], {"CREATE": 1, "REUSE": 1, "REJECT": 0})
        self.assertEqual(list(MigrationRowRecord.objects.order_by("pk").values()), original_history)
        self.assertEqual(self.upload(domain, "import", body).data["counts"]["CREATE"], 0)

    def prepare_classes(self):
        self.assertEqual(self.upload("classes", "import", "class_level,class_arm\nJSS1,A").data["counts"]["CREATE"], 1)
        session = AcademicSession.objects.create(school=self.school, name="2026/27", start_date="2026-09-01", end_date="2027-07-31", is_current=True)
        Term.objects.create(session=session, name="first", start_date="2026-09-01", end_date="2026-12-15", is_current=True)

    def test_partial_student_import_retries_without_duplicate_students_or_parents(self):
        self.prepare_classes()
        self.interrupted_import("students", "student_ref,first_name,last_name,class_level,class_arm,dob,guardian_name,guardian_phone\nONE,Ada,First,JSS1,A,2013-01-02,Guardian,08011111111\nTWO,Bea,Second,JSS1,A,2013-02-03,Guardian,08011111111")
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(), 2)
        self.assertEqual(SessionEnrollment.objects.filter(school=self.school).count(), 2)
        from accounts.models import ParentStudentLink
        parents = "first_name,last_name,email,phone\nShared,Guardian,parent@retry.invalid,08011111111"
        for _ in range(2):
            self.assertEqual(self.upload("parents", "import", parents).status_code, 200)
        self.interrupted_import("parent_links", "parent_email,student_ref,relationship\nparent@retry.invalid,ONE,guardian\nparent@retry.invalid,TWO,guardian")
        self.assertEqual(ParentStudentLink.objects.filter(school=self.school).count(), 2)
        self.assertEqual(ParentStudentLink.objects.filter(school=self.school).values("parent_id").distinct().count(), 1)

    def test_partial_staff_and_assignment_import_retries_without_duplicates(self):
        self.prepare_classes()
        self.interrupted_import("staff", "first_name,last_name,email\nTayo,First,first@retry.invalid\nBea,Second,second@retry.invalid")
        self.assertEqual(StaffProfile.objects.filter(school=self.school).count(), 2)
        self.upload("subjects", "import", "code,name,class_level\nMATH,Mathematics,JSS1\nENG,English,JSS1")
        self.interrupted_import("assignments", "teacher_email,class_level,class_arm,subject_code\nfirst@retry.invalid,JSS1,A,MATH\nsecond@retry.invalid,JSS1,A,ENG")
        self.assertEqual(SubjectAssignment.objects.filter(school=self.school).count(), 2)

    def test_partial_fee_schedule_import_retries_without_duplicate_obligations(self):
        self.prepare_classes()
        for name in ("Tuition", "Books"):
            FeeCategory.objects.create(school=self.school, name=name)
        self.interrupted_import("fee_schedules", "class_level,fee_category,amount,due_date\nJSS1,Tuition,50000,2026-10-31\nJSS1,Books,10000,2026-10-31")
        self.assertEqual(FeeSchedule.objects.filter(school=self.school).count(), 2)
        self.assertFalse(StudentLedgerEntry.objects.filter(school=self.school).exists())


class ResultRecoveryTests(TransactionTestCase):
    user = classmethod(result_fixtures.AcademicWorkflowTests.user.__func__)
    configure = result_fixtures.AcademicWorkflowTests.configure
    save_scores = result_fixtures.AcademicWorkflowTests.save_scores
    action = result_fixtures.AcademicWorkflowTests.action
    publish = result_fixtures.AcademicWorkflowTests.publish

    def setUp(self):
        result_fixtures.AcademicWorkflowTests.setUpTestData.__func__(type(self))
        result_fixtures.AcademicWorkflowTests.setUp(self)

    test_publish_retry_keeps_single_transition_history = result_fixtures.AcademicWorkflowTests.test_retry_transitions_keep_one_audit_event
    test_reopen_retry_keeps_single_transition_history = result_fixtures.AcademicWorkflowTests.test_reopen_retry_keeps_one_audit_event_and_requires_admin_reason

    def test_publish_reopen_conflict_remains_auditable(self):
        self.configure()
        self.save_scores()
        self.publish()
        entry = ScoreEntry.objects.get()
        original_total = entry.total_score
        barrier = Barrier(2)
        def request(action):
            try:
                client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
                client.force_authenticate(self.admin)
                barrier.wait(timeout=10)
                body = self.scope if action == "publish" else {"entry_ids": [entry.pk], "reason": "Correct the recorded exam score"}
                return client.post(f"/api/gradebook/entries/{action}/", body, format="json")
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            publish = pool.submit(request, "publish")
            reopen = pool.submit(request, "reopen")
            self.assertIn(publish.result(timeout=30).status_code, (200, 400))
            self.assertEqual(reopen.result(timeout=30).status_code, 200)
        entry.refresh_from_db()
        self.assertFalse(entry.is_published)
        self.assertEqual(entry.review_state, "draft")
        self.assertEqual(entry.total_score, original_total)
        self.assertEqual(PlatformEvent.objects.filter(action="school.results_publish").count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action="school.results_reopened").count(), 1)


class PresenceRecoveryTests(TestCase):
    setUpTestData = classmethod(presence_fixtures.Batch21PresenceTests.setUpTestData.__func__)
    client_for = presence_fixtures.Batch21PresenceTests.client_for

    def test_arrival_and_correction_retries_preserve_one_record(self):
        client = self.client_for(self.principal)
        body = {"student": self.student.pk}
        for _ in range(2):
            self.assertEqual(client.post("/api/attendance/presence/", body, format="json").status_code, 201)
        presence = StudentDailyPresence.objects.get(student=self.student)
        original = presence.arrival_at
        corrected = original.replace(second=(original.second + 1) % 60)
        payload = {"reason": "Gate register correction", "arrival_at": corrected.isoformat()}
        for _ in range(2):
            response = client.patch(f"/api/attendance/presence/{presence.pk}/correct/", payload, format="json")
            self.assertEqual(response.status_code, 200, response.data)
        presence.refresh_from_db()
        self.assertEqual(presence.arrival_at, corrected)
        self.assertEqual(StudentDailyPresence.objects.filter(student=self.student).count(), 1)
        audits = PlatformEvent.objects.filter(action="attendance.student_presence_corrected", target=f"presence:{presence.pk}")
        self.assertEqual(audits.count(), 1)
