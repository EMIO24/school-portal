"""Retirement owns the school lock before competing placement transactions."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from datetime import date

from django.db import connection, transaction
from django.test import TransactionTestCase

from enrollment.class_structure import ensure_default_arm, ClassStructureError
from enrollment.transfers import transfer_student, StudentTransferError
from enrollment.models import ClassArm, SessionEnrollment, Subject, SubjectAssignment
from academics.models import Term
from enrollment.session_enrollment import ensure_current_enrollment, EnrollmentPlacementError
from .models import School, Campus
from . import test_batch26c_campus_history as fixtures


class Batch26DCampusRaces(TransactionTestCase):
    setUp = fixtures.Batch26CCampusTests.setUp
    client_for = fixtures.Batch26CCampusTests.client_for

    def race(self, operation):
        started = Event()
        worker_pid = []

        def worker():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '15s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    worker_pid.append(cursor.fetchone()[0])
                started.set()
                return operation()
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                School.objects.select_for_update().get(pk=self.school.pk)
                Campus.objects.filter(pk=self.campus.pk).update(is_active=False)
                future = pool.submit(worker)
                self.assertTrue(started.wait(10))
                deadline = monotonic() + 10
                waiting = False
                while monotonic() < deadline and not future.done():
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_stat_clear_snapshot()")
                        cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", worker_pid)
                        row = cursor.fetchone()
                    if row and row[0] == "Lock":
                        waiting = True
                        break
                    sleep(0.02)
                self.assertTrue(waiting or future.done(), "Placement did not reach its database boundary")
            result = future.result(timeout=20)
        self.assertTrue(Campus.objects.filter(pk=self.campus.pk, is_active=False).exists())
        return result

    def test_retirement_vs_staff_campus_assignment(self):
        self.staff.campus = self.second
        self.staff.save(update_fields=["campus"])
        response = self.race(lambda: self.client_for().patch(
            f"/api/staff/{self.staff.pk}/", {"campus": self.campus.pk}, format="json"))
        self.assertEqual(response.status_code, 400, response.data)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.campus_id, self.second.pk)

    def test_retirement_vs_class_creation(self):
        response = self.race(lambda: self.client_for().post("/api/class-arms/", {
            "class_level": self.level.pk, "campus": self.campus.pk, "name": "RACE"}, format="json"))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(ClassArm.objects.filter(name="RACE").exists())

    def test_retirement_vs_staff_class_assignment(self):
        response = self.race(lambda: self.client_for().post(
            f"/api/staff/{self.staff.pk}/assign-classes/", {"classes": [self.arm.pk]}, format="json"))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(self.staff.assigned_classes.exists())

    def test_retirement_vs_initial_student_placement(self):
        self.enrollment.delete()
        def place():
            with self.assertRaises(EnrollmentPlacementError):
                ensure_current_enrollment(school=self.school, student=self.student, class_arm=self.arm, actor=self.admin)
        self.race(place)
        self.assertFalse(SessionEnrollment.objects.filter(student=self.student).exists())

    def assignment_data(self):
        subject = Subject.objects.create(school=self.school, name="Math", code="MATH")
        term = Term.objects.create(session=self.session, name="first", start_date="2026-09-01", end_date="2026-12-15")
        return {"teacher": self.staff.pk, "subject": subject.pk, "class_arm": self.arm.pk,
                "session": self.session.pk, "term": term.pk}

    def test_retirement_vs_teaching_assignment(self):
        body = self.assignment_data()
        response = self.race(lambda: self.client_for().post("/api/subject-assignments/", body, format="json"))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(SubjectAssignment.objects.exists())

    def test_existing_teaching_assignment_replay_survives_retirement(self):
        body = self.assignment_data()
        assignment = SubjectAssignment.objects.create(school=self.school, teacher=self.staff,
            subject_id=body["subject"], class_arm=self.arm, session=self.session, term_id=body["term"])
        Campus.objects.filter(pk=self.campus.pk).update(is_active=False)
        response = self.client_for().post(f"/api/staff/{self.staff.pk}/assign-subjects/", {
            "session_id": self.session.pk, "term_id": body["term"],
            "assignments": [{"subject_id": body["subject"], "class_arm_id": self.arm.pk}]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(SubjectAssignment.objects.get().pk, assignment.pk)

    def test_retirement_vs_admission(self):
        response = self.race(lambda: self.client_for().post(
            f"/api/operations/admissions/{self.application.pk}/decision/",
            {"decision": "admit", "class_arm": self.arm.pk}, format="json"))
        self.assertEqual(response.status_code, 400, response.data)
        self.application.refresh_from_db()
        self.assertIsNone(self.application.admitted_student_id)

    def test_retirement_vs_cached_no_arm_default_creation(self):
        self.school.uses_class_arms = False
        self.school.save(update_fields=["uses_class_arms"])
        def create():
            with self.assertRaises(ClassStructureError):
                ensure_default_arm(school=self.school, class_level=self.level, campus=self.campus)
        self.race(create)
        self.assertFalse(ClassArm.objects.filter(campus=self.campus, is_default=True).exists())

    def test_retirement_vs_transfer(self):
        source = ClassArm.objects.create(school=self.school, class_level=self.level, campus=self.second, name="SOURCE")
        self.student.current_class = source
        self.student.save(update_fields=["current_class"])
        self.enrollment.class_arm = source
        self.enrollment.save(update_fields=["class_arm"])
        def transfer():
            with self.assertRaises(StudentTransferError):
                transfer_student(school=self.school, student=self.student, destination_class=self.arm,
                                 effective_date=date(2026, 9, 2), actor=self.admin)
        self.race(transfer)
        self.assertEqual(SessionEnrollment.objects.filter(student=self.student).count(), 1)
        self.student.refresh_from_db()
        self.assertEqual(self.student.current_class_id, source.pk)
