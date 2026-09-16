from django.test import SimpleTestCase
from .models import CustomUser
from .serializers import UserProfileSerializer
from enrollment.models import StudentProfile, StaffProfile
from enrollment.staff_serializers import StaffListSerializer


class FrontendProfileContractTests(SimpleTestCase):
    def test_student_profile_and_class_ids_are_distinct_from_account_id(self):
        user = CustomUser(id=41, role='student', email='student@example.com')
        StudentProfile(id=7, user=user, current_class_id=12)
        data = UserProfileSerializer(user).data
        self.assertEqual(data['id'], 41)
        self.assertEqual(data['student_id'], 7)
        self.assertEqual(data['class_arm_id'], 12)

    def test_non_student_profile_has_nullable_student_fields(self):
        user = CustomUser(role='teacher', email='teacher@example.com')
        data = UserProfileSerializer(user).data
        self.assertIsNone(data['student_id'])
        self.assertIsNone(data['class_arm_id'])

    def test_staff_list_exposes_user_id_for_timetable_assignments(self):
        user = CustomUser(id=41, role='teacher', email='teacher@example.com')
        staff = StaffProfile(id=7, user=user)
        data = StaffListSerializer(staff).data
        self.assertEqual(data['id'], 7)
        self.assertEqual(data['user'], 41)

    def test_student_list_identifies_profile_and_gradebook_account_separately(self):
        from enrollment.serializers import StudentListSerializer
        from gradebook.models import ScoreEntry
        from attendance.models import AttendanceRecord
        student = StudentProfile(id=7, user=CustomUser(id=41, role='student'))
        data = StudentListSerializer(student).data
        self.assertEqual(data['id'], 7)
        self.assertEqual(data['user'], 41)
        self.assertIs(ScoreEntry._meta.get_field('student').related_model, CustomUser)
        self.assertIs(AttendanceRecord._meta.get_field('student').related_model, CustomUser)
