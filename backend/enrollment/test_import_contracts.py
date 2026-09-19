from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import resolve
from rest_framework.test import APIRequestFactory, force_authenticate
from accounts.models import CustomUser
from tenants.models import School
from .models import StaffProfile, StudentProfile


class StaffImportContractTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Contract School', slug='contract', subdomain='contract')
        self.admin = CustomUser.objects.create_user(email='admin@contract.test', password='test', role='school_admin', must_change_password=False, school=self.school)
        self.factory = APIRequestFactory()

    def upload(self, content, filename='staff.csv', user=None):
        request = self.factory.post('/api/staff/bulk-import/', {
            'file': SimpleUploadedFile(filename, content.encode('utf-8'), content_type='application/pdf'),
        }, format='multipart')
        request.tenant = self.school
        force_authenticate(request, user=user or self.admin)
        return resolve('/api/staff/bulk-import/').func(request)

    def test_staff_only_headers_create_staff_and_no_students(self):
        response = self.upload('first_name,last_name,email,role\nAda,Okafor,ada@contract.test,teacher', 'STAFF.CSV')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {'success_count': 1, 'error_count': 0, 'errors': []})
        profile = StaffProfile.objects.get(user__email='ada@contract.test')
        self.assertTrue(profile.user.must_change_password)
        self.assertTrue(profile.user.check_password(profile.staff_id))
        self.assertEqual(StudentProfile.objects.count(), 0)

    def test_invalid_role_does_not_create_an_account(self):
        response = self.upload('first_name,last_name,email,role\nAda,Okafor,ada@contract.test,student')
        self.assertEqual(response.data['success_count'], 0)
        self.assertEqual(response.data['error_count'], 1)
        self.assertFalse(CustomUser.objects.filter(email='ada@contract.test').exists())

    def test_missing_headers_rejected_before_any_import(self):
        response = self.upload('first_name,email\nAda,ada@contract.test')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(StaffProfile.objects.count(), 0)

    def test_duplicate_rows_report_partial_success(self):
        row = 'Ada,Okafor,ada@contract.test,teacher'
        response = self.upload('first_name,last_name,email,role\n' + row + '\n' + row)
        self.assertEqual(response.data['success_count'], 1)
        self.assertEqual(response.data['errors'][0]['row'], 3)

    def test_teacher_cannot_bulk_import_staff(self):
        teacher = CustomUser.objects.create_user(email='teacher@contract.test', password='test', role='teacher', school=self.school)
        response = self.upload('first_name,last_name,email,role\nAda,Okafor,ada@contract.test,teacher', user=teacher)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(StaffProfile.objects.count(), 0)

    def test_admin_from_another_school_cannot_import(self):
        school = School.objects.create(name='Other School', slug='other', subdomain='other')
        admin = CustomUser.objects.create_user(email='admin@other.test', password='test', role='school_admin', must_change_password=False, school=school)
        response = self.upload('first_name,last_name,email,role\nAda,Okafor,ada@contract.test,teacher', user=admin)
        self.assertEqual(response.status_code, 403)

    def test_attendance_csv_download_uses_a_non_renderer_query_parameter(self):
        request = self.factory.get('/api/attendance/sessions/class-report/?class_arm=1&term=1&download=csv')
        request.tenant = self.school
        force_authenticate(request, user=self.admin)
        response = resolve('/api/attendance/sessions/class-report/').func(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))

    def test_parent_children_response_includes_both_identifiers(self):
        from accounts.models import ParentStudentLink
        parent = CustomUser.objects.create_user(email='parent@contract.test', password='test', role='parent', school=self.school)
        student_user = CustomUser.objects.create_user(id=41, email='student@contract.test', password='test', role='student', school=self.school)
        student = StudentProfile.objects.create(id=7, user=student_user, school=self.school)
        ParentStudentLink.objects.create(parent=parent, student=student, school=self.school)
        request = self.factory.get('/api/parent/children/')
        request.tenant = self.school
        force_authenticate(request, user=parent)
        response = resolve('/api/parent/children/').func(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['student_id'], 7)
        self.assertEqual(response.data[0]['user_id'], 41)
