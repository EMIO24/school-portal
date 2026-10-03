"""Institutional ID history and real PostgreSQL allocation races."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from academics.models import AcademicSession
from tenants.models import PlatformEvent, School
from .models import (
    AdmissionApplication, ClassArm, ClassLevel, InstitutionalIdentifierSequence,
    SessionEnrollment, StaffProfile, StudentProfile, StudentRecordEntry,
)
from .utils import MAX_IDENTIFIER_SEQUENCE, generate_admission_number, generate_staff_id


class IdentifierFixtures:
    def setUp(self):
        super().setUp()
        self.school = School.objects.create(
            name="Identifier School", slug="identifier-school",
            subdomain="identifier-school", subscription_plan="enterprise",
        )
        self.admin = self.user("admin", role="school_admin")
        today = timezone.localdate()
        self.session = AcademicSession.objects.create(
            school=self.school, name="Identifier Session", is_current=True,
            start_date=today - timedelta(days=30), end_date=today + timedelta(days=300),
        )
        self.level = ClassLevel.objects.create(school=self.school, name="JSS1")
        self.arm = ClassArm.objects.create(school=self.school, class_level=self.level, name="A")

    def user(self, label, role="student", school=None):
        return get_user_model().objects.create_user(
            email=f"{label}@identifiers.invalid", password=None,
            school=school or self.school, role=role,
            first_name=label, last_name="Identifier", must_change_password=False,
        )

    @property
    def student_prefix(self):
        return f"{self.school.slug.upper()}-{date.today().year}-"

    @property
    def staff_prefix(self):
        return f"{self.school.slug.upper()}-STAFF-"

    def student(self, label, number=None, school=None):
        school = school or self.school
        fields = {"admission_number": number} if number else {}
        return StudentProfile.objects.create(
            school=school, user=self.user(label, school=school), **fields,
        )

    def staff(self, label, number=None, school=None):
        school = school or self.school
        fields = {"staff_id": number} if number else {}
        return StaffProfile.objects.create(
            school=school, user=self.user(label, role="teacher", school=school), **fields,
        )

    def application(self, label):
        return AdmissionApplication.objects.create(
            school=self.school, first_name=label, last_name="Applicant",
            guardian_name="Guardian", guardian_phone="08000000000",
            applying_class_level=self.level,
        )


class IdentifierHistoryTests(IdentifierFixtures, TestCase):
    def test_student_sequence_bootstraps_numeric_history_above_9999(self):
        legacy = self.student("legacy9999", self.student_prefix + "9999")
        first = self.student("next10000")
        second = self.student("next10001")
        self.assertEqual(first.admission_number, self.student_prefix + "10000")
        self.assertEqual(second.admission_number, self.student_prefix + "10001")
        legacy.refresh_from_db()
        self.assertEqual(legacy.admission_number, self.student_prefix + "9999")

    def test_staff_sequence_bootstraps_numeric_history_above_9999(self):
        legacy = self.staff("staff9999", self.staff_prefix + "9999")
        first = self.staff("staff10000")
        second = self.staff("staff10001")
        self.assertEqual(first.staff_id, self.staff_prefix + "10000")
        self.assertEqual(second.staff_id, self.staff_prefix + "10001")
        legacy.refresh_from_db()
        self.assertEqual(legacy.staff_id, self.staff_prefix + "9999")

    def test_later_imports_raise_high_water_without_rewriting_custom_ids(self):
        for create, prefix, field in (
            (self.student, self.student_prefix, "admission_number"),
            (self.staff, self.staff_prefix, "staff_id"),
        ):
            with self.subTest(field=field):
                create(field + "first")
                imported = create(field + "import", prefix + "10000")
                custom = create(field + "custom", prefix + "CUSTOM")
                next_profile = create(field + "next")
                self.assertEqual(getattr(next_profile, field), prefix + "10001")
                imported.refresh_from_db()
                custom.refresh_from_db()
                self.assertEqual(getattr(imported, field), prefix + "10000")
                self.assertEqual(getattr(custom, field), prefix + "CUSTOM")

    def test_maximum_slug_staff_ids_fit_storage_and_default_password(self):
        from .staff_serializers import StaffProfileSerializer

        self.school.slug = "s" * 100
        self.school.save(update_fields=["slug"])
        request = APIRequestFactory().post("/api/staff/", {}, format="json")
        request.tenant = self.school
        request.user = self.admin
        serializer = StaffProfileSerializer(data={
            "new_email": "longstaff@identifiers.invalid", "new_first_name": "Long",
            "new_last_name": "Staff", "new_role": "teacher",
        }, context={"request": request})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        profile = serializer.save(school=self.school)
        self.assertEqual(profile.staff_id, self.staff_prefix + "0001")
        self.assertEqual(len(profile.staff_id), 111)
        self.assertTrue(profile.user.check_password(profile.staff_id))
        self.staff("last-seeded", self.staff_prefix + str(MAX_IDENTIFIER_SEQUENCE - 1))
        last = self.staff("last-generated")
        self.assertEqual(last.staff_id, self.staff_prefix + str(MAX_IDENTIFIER_SEQUENCE))
        self.assertEqual(len(last.staff_id), 126)
        self.assertLessEqual(len(last.staff_id), StaffProfile._meta.get_field("staff_id").max_length)

    def test_historical_ids_survive_identity_and_school_configuration_changes(self):
        student = self.student("history-student")
        staff = self.staff("history-staff")
        original = (student.admission_number, staff.staff_id)
        self.school.slug = "renamed-school"
        self.school.save(update_fields=["slug"])
        student.user.first_name = "Corrected"
        student.user.save(update_fields=["first_name"])
        student.guardian_name = "Corrected Guardian"
        student.save()
        staff.phone = "08001112222"
        staff.save()
        student.refresh_from_db()
        staff.refresh_from_db()
        self.assertEqual((student.admission_number, staff.staff_id), original)
        renamed = self.student("renamed-student")
        self.assertTrue(renamed.admission_number.startswith(self.student_prefix))
        self.school.slug = "identifier-school"
        self.school.save(update_fields=["slug"])
        resumed = self.student("resumed-student")
        self.assertEqual(resumed.admission_number, self.student_prefix + "0002")

    def test_committed_reservations_are_not_recycled_before_insertion_or_after_deletion(self):
        for generator, create, prefix, field in (
            (generate_admission_number, self.student, self.student_prefix, "admission_number"),
            (generate_staff_id, self.staff, self.staff_prefix, "staff_id"),
        ):
            with self.subTest(field=field):
                self.assertEqual(generator(self.school), prefix + "0001")
                self.assertEqual(generator(self.school), prefix + "0002")
                profile = create(field + "reserved")
                self.assertEqual(getattr(profile, field), prefix + "0003")
                profile.delete()
                self.assertEqual(generator(self.school), prefix + "0004")

    def test_exhausted_sequences_fail_closed_without_mutating_history(self):
        for generator, create, prefix, field in (
            (generate_admission_number, self.student, self.student_prefix, "admission_number"),
            (generate_staff_id, self.staff, self.staff_prefix, "staff_id"),
        ):
            with self.subTest(field=field):
                issued = create(field + "exhausted", prefix + str(MAX_IDENTIFIER_SEQUENCE))
                with self.assertRaisesMessage(ValidationError, "capacity is exhausted"):
                    generator(self.school)
                issued.refresh_from_db()
                self.assertEqual(getattr(issued, field), prefix + str(MAX_IDENTIFIER_SEQUENCE))
                self.assertFalse(InstitutionalIdentifierSequence.objects.filter(namespace=prefix).exists())

    def test_normalized_slug_collision_bootstraps_other_school_history_without_cross_link(self):
        other = School.objects.create(
            name="Other Identifier School", slug=self.school.slug.upper(),
            subdomain="other-identifier-school", subscription_plan="enterprise",
        )
        for create, prefix, field in (
            (self.student, self.student_prefix, "admission_number"),
            (self.staff, self.staff_prefix, "staff_id"),
        ):
            with self.subTest(field=field):
                original = create(field + "other", prefix + "9999", school=other)
                new = create(field + "own")
                self.assertEqual(getattr(new, field), prefix + "10000")
                self.assertEqual(new.school_id, self.school.pk)
                self.assertEqual(new.user.school_id, self.school.pk)
                self.assertNotEqual(new.pk, original.pk)
                original.refresh_from_db()
                self.assertEqual(original.school_id, other.pk)
                self.assertEqual(getattr(original, field), prefix + "9999")

    def test_prior_year_identifiers_do_not_advance_new_year_sequence(self):
        old = self.student("prior-year", f"{self.school.slug.upper()}-{date.today().year - 1}-9999")
        new = self.student("new-year")
        self.assertEqual(new.admission_number, self.student_prefix + "0001")
        old.refresh_from_db()
        self.assertTrue(old.admission_number.endswith("-9999"))


@skipUnless(connection.vendor == "postgresql", "Real PostgreSQL identifier concurrency required")
class IdentifierPostgresConcurrencyTests(IdentifierFixtures, TransactionTestCase):
    def concurrent(self, jobs):
        barrier = Barrier(len(jobs))

        def run(job):
            close_old_connections()
            try:
                # Independent connections and real transactions, bounded waits.
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '15s'")
                    cursor.execute("SET statement_timeout = '30s'")
                barrier.wait(timeout=15)
                return job()
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            futures = [pool.submit(run, job) for job in jobs]
            return [future.result(timeout=60) for future in futures]

    def decide(self, application):
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.subdomain)
        client.force_authenticate(self.admin)
        response = client.post(
            f"/api/operations/admissions/{application.pk}/decision/",
            {"decision": "admit", "class_arm": self.arm.pk}, format="json",
        )
        self.assertIn(response.status_code, (200, 201), getattr(response, "data", response.content))
        return response.status_code, response.data["admitted_student"]

    def assert_admission_history(self, count):
        students = StudentProfile.objects.filter(school=self.school)
        self.assertEqual(students.count(), count)
        self.assertEqual(len(set(students.values_list("admission_number", flat=True))), count)
        self.assertEqual(SessionEnrollment.objects.filter(school=self.school).count(), count)
        self.assertEqual(StudentRecordEntry.objects.filter(school=self.school).count(), count)
        self.assertEqual(PlatformEvent.objects.filter(action="admissions.student_admitted").count(), count)
        for student in students:
            self.assertEqual(student.user.school_id, self.school.pk)
            self.assertEqual(SessionEnrollment.objects.filter(student=student, session=self.session).count(), 1)
            self.assertEqual(StudentRecordEntry.objects.filter(student=student).count(), 1)

    def test_simultaneous_first_admissions_keep_distinct_ids_and_history(self):
        apps = [self.application(f"First{i}") for i in range(2)]
        # Start both independent requests together. Placement now serializes on
        # the school before allocation; an allocator barrier would deadlock that
        # valid ordering. Direct allocator races remain covered below.
        results = self.concurrent([lambda app=app: self.decide(app) for app in apps])
        self.assertEqual([status for status, _ in results], [201, 201])
        self.assert_admission_history(2)
        suffixes = [int(n.rsplit("-", 1)[1]) for n in StudentProfile.objects.values_list("admission_number", flat=True)]
        self.assertEqual(sorted(suffixes), [1, 2])

    def test_multiple_concurrent_admissions_after_existing_admission(self):
        self.assertEqual(self.decide(self.application("Existing"))[0], 201)
        apps = [self.application(f"Later{i}") for i in range(4)]
        self.concurrent([lambda app=app: self.decide(app) for app in apps])
        self.assert_admission_history(5)
        suffixes = [int(n.rsplit("-", 1)[1]) for n in StudentProfile.objects.values_list("admission_number", flat=True)]
        self.assertEqual(sorted(suffixes), [1, 2, 3, 4, 5])

    def test_simultaneous_same_application_retries_create_one_student(self):
        app = self.application("Retry")
        results = self.concurrent([lambda: self.decide(app), lambda: self.decide(app)])
        self.assertEqual(sorted(status for status, _ in results), [200, 201])
        self.assertEqual(len(set(pk for _, pk in results)), 1)
        self.assert_admission_history(1)
        student = StudentProfile.objects.get()
        number = student.admission_number
        self.assertEqual(self.decide(app), (200, student.pk))
        student.refresh_from_db()
        self.assertEqual(student.admission_number, number)
        self.assert_admission_history(1)

    def test_concurrent_staff_creation_preserves_ids_and_owner(self):
        def create(index):
            client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.subdomain)
            client.force_authenticate(self.admin)
            response = client.post("/api/staff/", {
                "new_email": f"staff{index}@identifiers.invalid", "new_role": "teacher",
                "new_first_name": f"Staff{index}", "new_last_name": "Concurrent",
            }, format="json")
            self.assertEqual(response.status_code, 201, response.data)
            return response.data["id"]

        # Request-start synchronization permits the operational school lock.
        self.concurrent([lambda i=i: create(i) for i in range(3)])
        self.assertEqual(StaffProfile.objects.count(), 3)
        numbers = list(StaffProfile.objects.values_list("staff_id", flat=True))
        self.assertEqual(len(set(numbers)), 3)
        self.assertEqual(sorted(int(n.rsplit("-", 1)[1]) for n in numbers), [1, 2, 3])
        for staff in StaffProfile.objects.all():
            number = staff.staff_id
            self.assertEqual(staff.school_id, self.school.pk)
            self.assertEqual(staff.user.school_id, self.school.pk)
            self.assertTrue(staff.user.check_password(number))
            staff.phone = "08009998888"
            staff.save()
            staff.refresh_from_db()
            self.assertEqual(staff.staff_id, number)

    def test_helper_reservations_survive_lock_release_before_profile_insertion(self):
        for generator, model, field, role in (
            (generate_admission_number, StudentProfile, "admission_number", "student"),
            (generate_staff_id, StaffProfile, "staff_id", "teacher"),
        ):
            with self.subTest(field=field):
                insertion_barrier = Barrier(2)

                def create(index):
                    number = generator(self.school)
                    self.assertFalse(connection.in_atomic_block)
                    insertion_barrier.wait(timeout=15)
                    profile = model.objects.create(
                        school=self.school, user=self.user(f"{field}{index}", role=role),
                        **{field: number},
                    )
                    return profile.pk, number

                results = self.concurrent([lambda i=i: create(i) for i in range(2)])
                self.assertEqual(len(set(number for _, number in results)), 2)
                self.assertEqual(model.objects.filter(school=self.school).count(), 2)

    def test_concurrent_case_normalized_school_prefixes_do_not_collide(self):
        other = School.objects.create(
            name="Case Variant", slug=self.school.slug.upper(),
            subdomain="case-variant", subscription_plan="enterprise",
        )
        for model, field, role in (
            (StudentProfile, "admission_number", "student"),
            (StaffProfile, "staff_id", "teacher"),
        ):
            with self.subTest(field=field):
                def create(school):
                    with transaction.atomic():
                        profile = model.objects.create(
                            school=school, user=self.user(f"{field}{school.pk}", role=role, school=school),
                        )
                        return profile.pk, getattr(profile, field)

                results = self.concurrent([lambda: create(self.school), lambda: create(other)])
                self.assertEqual(len(set(number for _, number in results)), 2)
                for (pk, _), school in zip(results, (self.school, other)):
                    profile = model.objects.get(pk=pk)
                    self.assertEqual(profile.school_id, school.pk)
                    self.assertEqual(profile.user.school_id, school.pk)
