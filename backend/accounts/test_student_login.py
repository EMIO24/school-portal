from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from enrollment.models import ClassLevel, StudentProfile
from tenants.models import School


class StudentNameLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name="Cedarfield", slug="cedarfield", subdomain="cedarfield", subscription_plan="premium")
        cls.other_school = School.objects.create(name="Bright Future", slug="bright", subdomain="bright", subscription_plan="premium")
        cls.password = "Student-password!26"
        cls.student = cls.make_student(cls.school, "legacy@student.invalid")
        cls.foreign = cls.make_student(cls.other_school)
        cls.admin = get_user_model().objects.create_user(email="admin@login.invalid", password=cls.password,
                                                        role="school_admin", school=cls.school, must_change_password=False)

    @classmethod
    def make_student(cls, school, email=None, first="Emmanuel", last="Osarodion"):
        user = get_user_model().objects.create_user(email=email, password=cls.password, role="student", school=school,
                                                   first_name=first, last_name=last, must_change_password=False)
        StudentProfile.objects.create(user=user, school=school)
        return user

    def login(self, identifier, school=None, password=None, admission=None):
        cache.clear()
        client = APIClient(HTTP_X_SCHOOL_SLUG=(school or self.school).slug)
        payload = {"email": identifier, "password": password or self.password}
        if admission is not None:
            payload["admission_number"] = admission
        return client.post("/api/auth/login/", payload, format="json")

    def admin_client(self):
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(self.admin).access_token))
        return client

    def assert_invalid(self, response):
        self.assertEqual(response.status_code, 401, response.data)
        self.assertEqual(response.json(), {"errors": {"non_field_errors": ["Invalid login details."]}})

    def test_name_case_and_whitespace_preserve_display_name(self):
        for name in ("Emmanuel Osarodion", "emmanuel osarodion", "EMMANUEL OSARODION",
                     "eMmAnUeL oSaRoDiOn", "  Emmanuel   Osarodion  ", "Emmanuel\tOsarodion"):
            with self.subTest(name=name):
                response = self.login(name)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data["user"]["id"], self.student.pk)
                self.assertEqual(response.data["user"]["full_name"], "Emmanuel Osarodion")
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Emmanuel")
        self.assertEqual(self.student.last_name, "Osarodion")
        self.assertEqual(self.student.email, "legacy@student.invalid")

    def test_same_name_in_different_schools_is_scoped(self):
        response = self.login("Emmanuel Osarodion", school=self.other_school)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["id"], self.foreign.pk)
        self.foreign.set_password("Other-password!26")
        self.foreign.save()
        self.assert_invalid(self.login("Emmanuel Osarodion", school=self.other_school))

    def test_name_requires_school_and_password_errors_are_generic(self):
        self.assert_invalid(self.login("Emmanuel Osarodion", password="incorrect"))
        self.assert_invalid(self.login("No Such Student"))
        cache.clear()
        self.assert_invalid(APIClient().post("/api/auth/login/", {"email": "Emmanuel Osarodion", "password": self.password}, format="json"))

    def test_inactive_user_profile_and_suspended_school_are_denied(self):
        self.student.is_active = False
        self.student.save()
        self.assert_invalid(self.login("Emmanuel Osarodion"))
        self.student.is_active = True
        self.student.save()
        profile = self.student.student_profile
        profile.status = "suspended"
        profile.save()
        self.assert_invalid(self.login("Emmanuel Osarodion"))
        profile.status = "active"
        profile.save()
        self.school.is_active = False
        self.school.save()
        self.assert_invalid(self.login("Emmanuel Osarodion"))
        self.assertNotEqual(self.login(self.student.email).status_code, 200)

    def test_duplicates_never_select_first_and_identifier_is_private(self):
        duplicate = self.make_student(self.school)
        for password in (self.password, "incorrect"):
            self.assert_invalid(self.login("Emmanuel Osarodion", password=password))
        for user in (self.student, duplicate):
            response = self.login("emmanuel osarodion", admission=user.student_profile.admission_number)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["user"]["id"], user.pk)
        self.assert_invalid(self.login("Emmanuel Osarodion", admission="unknown"))
        self.assert_invalid(self.login("Emmanuel Osarodion", admission=self.foreign.student_profile.admission_number))
        self.assert_invalid(self.login("Wrong Name", admission=duplicate.student_profile.admission_number))
        self.assert_invalid(self.login("Emmanuel Osarodion", admission=duplicate.student_profile.admission_number, password="incorrect"))

    def test_inactive_duplicate_does_not_block_unique_active_student(self):
        duplicate = self.make_student(self.school)
        duplicate.is_active = False
        duplicate.save()
        self.assertEqual(self.login("Emmanuel Osarodion").status_code, 200)

    def test_admin_creates_email_less_students_who_can_login(self):
        for index in range(2):
            response = self.admin_client().post("/api/students/", {"new_first_name": "New", "new_last_name": f"Student{index}"}, format="json")
            self.assertEqual(response.status_code, 201, response.data)
            user = get_user_model().objects.get(pk=response.data["user"])
            self.assertIsNone(user.email)
            self.assertTrue(user.must_change_password)
            login = self.login(f"New Student{index}", password=response.data["admission_number"])
            self.assertEqual(login.status_code, 200, login.data)
            self.assertEqual(login.data["user"]["id"], user.pk)

    def test_csv_import_without_email_produces_usable_account(self):
        ClassLevel.objects.create(school=self.school, name="JSS1")
        csv = b"first_name,last_name,gender,dob,class_level,guardian_name,guardian_phone\nCSV,Student,,,JSS1,,"
        response = self.admin_client().post("/api/students/bulk-import/", {"file": SimpleUploadedFile("students.csv", csv, content_type="text/csv")}, format="multipart")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["success_count"], 1, response.data)
        profile = StudentProfile.objects.get(user__first_name="CSV")
        self.assertIsNone(profile.user.email)
        self.assertEqual(self.login("CSV Student", password=profile.admission_number).status_code, 200)

    def test_existing_email_and_other_role_logins_remain_available(self):
        self.assertEqual(self.login(self.student.email).status_code, 200)
        for role in ("parent", "teacher", "school_admin"):
            user = get_user_model().objects.create_user(email=f"{role}@login.invalid", password=self.password,
                first_name="Role", last_name=role, role=role, school=self.school)
            response = self.login(user.email)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["user"]["id"], user.pk)
            self.assert_invalid(self.login(f"Role {role}"))

    def test_platform_email_still_enters_existing_mfa_flow(self):
        from rest_framework.response import Response
        owner = get_user_model().objects.create_superuser("owner@login.invalid", self.password)
        with patch("tenants.security.start_challenge", return_value=Response({"mfa_required": True}, status=202)) as challenge:
            response = self.login(owner.email)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(challenge.call_args.args[0].pk, owner.pk)

    def test_nonstudent_email_requirement_and_existing_uniqueness_remain(self):
        for role in ("teacher", "parent", "school_admin", "superadmin"):
            with self.assertRaises(ValueError):
                get_user_model().objects.create_user(role=role)
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create(role="teacher", email=None)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.make_student(self.school, email=self.student.email)

    def test_email_less_creation_requires_name_and_school_admin(self):
        response = self.admin_client().post("/api/students/", {}, format="json")
        self.assertEqual(response.status_code, 400)
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        client.force_authenticate(self.student)
        response = client.post("/api/students/", {"new_first_name": "New", "new_last_name": "Student"}, format="json")
        self.assertEqual(response.status_code, 403)
