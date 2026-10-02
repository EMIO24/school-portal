from datetime import date, datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from academics.models import AcademicSession, Term
from accounts.models import ParentStudentLink
from attendance.models import AttendanceRecord, AttendanceSession, StudentDailyPresence
from enrollment.models import ClassArm, ClassLevel, SessionEnrollment, StaffProfile, StudentProfile
from tenants.models import PlatformEvent, School


User = get_user_model()


class Batch21PresenceAndRolesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(
            name='Batch 21 School', slug='batch21', subdomain='batch21',
            subscription_plan='basic', arrival_cutoff_time=time(7, 45),
        )
        cls.other_school = School.objects.create(
            name='Other Batch 21 School', slug='other-batch21', subdomain='other-batch21',
            subscription_plan='basic',
        )
        cls.admin = User.objects.create_user(
            email='admin@batch21.test', password='Password!123', school=cls.school,
            role='school_admin', first_name='Admin', last_name='One', must_change_password=False,
        )
        cls.principal = User.objects.create_user(
            email='principal@batch21.test', password='Password!123', school=cls.school,
            role='principal', first_name='Pat', last_name='Principal', must_change_password=False,
        )
        cls.class_teacher = User.objects.create_user(
            email='classteacher@batch21.test', password='Password!123', school=cls.school,
            role='class_teacher', first_name='Chi', last_name='Teacher', must_change_password=False,
        )
        cls.other_class_teacher = User.objects.create_user(
            email='otherteacher@batch21.test', password='Password!123', school=cls.school,
            role='class_teacher', first_name='Other', last_name='Teacher', must_change_password=False,
        )
        StaffProfile.objects.create(user=cls.class_teacher, school=cls.school, employment_status='active')
        StaffProfile.objects.create(user=cls.other_class_teacher, school=cls.school, employment_status='active')
        cls.parent = User.objects.create_user(
            email='parent@batch21.test', password='Password!123', school=cls.school,
            role='parent', first_name='Parent', last_name='One', must_change_password=False,
        )
        cls.other_parent = User.objects.create_user(
            email='parent2@batch21.test', password='Password!123', school=cls.school,
            role='parent', first_name='Parent', last_name='Two', must_change_password=False,
        )
        cls.session = AcademicSession.objects.create(
            school=cls.school, name='2026/2027', start_date=date(2026, 9, 1),
            end_date=date(2027, 7, 31), is_current=True,
        )
        cls.term = Term.objects.create(
            session=cls.session, name='first', start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 18), is_current=True,
        )
        cls.level = ClassLevel.objects.create(school=cls.school, name='JSS1', order_index=1)
        cls.arm = ClassArm.objects.create(
            school=cls.school, class_level=cls.level, name='A', class_teacher=cls.class_teacher,
        )
        cls.other_arm = ClassArm.objects.create(
            school=cls.school, class_level=cls.level, name='B', class_teacher=cls.other_class_teacher,
        )
        cls.student_user = User.objects.create_user(
            email='student@batch21.test', password='Password!123', school=cls.school,
            role='student', first_name='Ada', last_name='Student', must_change_password=False,
        )
        cls.student = StudentProfile.objects.create(
            user=cls.student_user, school=cls.school, current_class=cls.arm,
        )
        cls.other_student_user = User.objects.create_user(
            email='student2@batch21.test', password='Password!123', school=cls.school,
            role='student', first_name='Ben', last_name='Student', must_change_password=False,
        )
        cls.other_student = StudentProfile.objects.create(
            user=cls.other_student_user, school=cls.school, current_class=cls.other_arm,
        )
        SessionEnrollment.objects.create(
            school=cls.school, student=cls.student, session=cls.session, class_arm=cls.arm,
            status='active', entry_reason='admission', enrolled_on=date(2026, 9, 1),
        )
        SessionEnrollment.objects.create(
            school=cls.school, student=cls.other_student, session=cls.session, class_arm=cls.other_arm,
            status='active', entry_reason='admission', enrolled_on=date(2026, 9, 1),
        )
        ParentStudentLink.objects.create(
            parent=cls.parent, student=cls.student, school=cls.school, relationship='guardian',
        )

    def client_for(self, user):
        client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        client.force_authenticate(user)
        return client

    def test_principal_can_read_command_centre_and_class_teacher_is_homeroom_scoped(self):
        response = self.client_for(self.principal).get('/api/principal/', {'section': 'snapshot'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['active_teachers'], 2)

        settings = self.client_for(self.class_teacher).get('/api/attendance/presence/settings/')
        self.assertEqual(settings.status_code, 200, settings.data)
        self.assertEqual(settings.data['classes'], [{'id': self.arm.pk, 'name': self.arm.full_name}])

        own = self.client_for(self.class_teacher).get('/api/attendance/presence/', {'class_arm': self.arm.pk})
        self.assertEqual(own.status_code, 200, own.data)
        self.assertEqual([row['student_id'] for row in own.data['students']], [self.student.pk])

        foreign = self.client_for(self.class_teacher).get('/api/attendance/presence/', {'class_arm': self.other_arm.pk})
        self.assertEqual(foreign.status_code, 403)

        student_list = self.client_for(self.class_teacher).get('/api/students/')
        ids = [row['id'] for row in (student_list.data.get('results', student_list.data) if isinstance(student_list.data, dict) else student_list.data)]
        self.assertIn(self.student.pk, ids)
        self.assertNotIn(self.other_student.pk, ids)

    def test_clockout_is_optional_idempotent_and_class_scoped(self):
        client = self.client_for(self.class_teacher)
        fixed_now = timezone.make_aware(datetime(2026, 10, 2, 8, 17), timezone.get_current_timezone())
        with patch('attendance.views.timezone.now', return_value=fixed_now), patch(
            'attendance.views.timezone.localdate', return_value=date(2026, 10, 2)
        ):
            arrival = client.post('/api/attendance/presence/', {'student': self.student.pk}, format='json')
            self.assertEqual(arrival.status_code, 201, arrival.data)
            self.assertTrue(arrival.data['late'])
            self.assertEqual(arrival.data['arrival_time'], '08:17')

            disabled = client.post('/api/attendance/presence/clock-out/', {'student': self.student.pk}, format='json')
            self.assertEqual(disabled.status_code, 403)

            denied = client.post('/api/attendance/presence/', {'student': self.other_student.pk}, format='json')
            self.assertEqual(denied.status_code, 403)

            enabled = self.client_for(self.admin).patch(
                '/api/attendance/presence/settings/',
                {'arrival_cutoff_time': '07:45', 'student_clockout_enabled': True},
                format='json',
            )
            self.assertEqual(enabled.status_code, 200, enabled.data)

            departure_time = timezone.make_aware(datetime(2026, 10, 2, 15, 26), timezone.get_current_timezone())
            with patch('attendance.views.timezone.now', return_value=departure_time):
                first = client.post('/api/attendance/presence/clock-out/', {'student': self.student.pk}, format='json')
                second = client.post('/api/attendance/presence/clock-out/', {'student': self.student.pk}, format='json')
            self.assertEqual(first.status_code, 200, first.data)
            self.assertEqual(second.status_code, 200, second.data)
            self.assertEqual(first.data['departure_at'], second.data['departure_at'])
            self.assertEqual(StudentDailyPresence.objects.filter(student=self.student, date=date(2026, 10, 2)).count(), 1)

    def test_late_attendance_time_is_visible_only_to_linked_parent(self):
        day = timezone.localdate()
        attendance = AttendanceSession.objects.create(
            school=self.school, class_arm=self.arm, teacher=self.class_teacher,
            term=self.term, date=day, mode='daily', is_finalized=True,
        )
        AttendanceRecord.objects.create(
            attendance_session=attendance, student=self.student_user, status='late',
        )
        arrival = timezone.make_aware(datetime.combine(day, time(8, 17)), timezone.get_current_timezone())
        departure = timezone.make_aware(datetime.combine(day, time(15, 26)), timezone.get_current_timezone())
        StudentDailyPresence.objects.create(
            school=self.school, student=self.student, date=day,
            arrival_at=arrival, arrival_recorded_by=self.class_teacher,
            departure_at=departure, departure_recorded_by=self.class_teacher,
        )
        self.school.student_clockout_enabled = True
        self.school.save(update_fields=['student_clockout_enabled'])

        linked = self.client_for(self.parent).get(f'/api/parent/dashboard/{self.student.pk}/')
        self.assertEqual(linked.status_code, 200, linked.data)
        self.assertEqual(linked.data['attendance_summary']['late'], 1)
        self.assertEqual(linked.data['presence_today']['arrival_time'], '08:17')
        self.assertTrue(linked.data['presence_today']['late'])
        self.assertEqual(linked.data['presence_today']['departure_time'], '15:26')

        unlinked = self.client_for(self.other_parent).get(f'/api/parent/dashboard/{self.student.pk}/')
        self.assertEqual(unlinked.status_code, 403)

    def test_presence_corrections_require_reason_and_are_audited(self):
        presence = StudentDailyPresence.objects.create(
            school=self.school, student=self.student, date=timezone.localdate(),
            arrival_at=timezone.now(), arrival_recorded_by=self.class_teacher,
        )
        denied = self.client_for(self.class_teacher).patch(
            f'/api/attendance/presence/{presence.pk}/correct/',
            {'reason': 'Correction', 'arrival_at': timezone.now().isoformat()},
            format='json',
        )
        self.assertEqual(denied.status_code, 403)

        missing_reason = self.client_for(self.principal).patch(
            f'/api/attendance/presence/{presence.pk}/correct/',
            {'arrival_at': timezone.now().isoformat()},
            format='json',
        )
        self.assertEqual(missing_reason.status_code, 400)

        new_time = timezone.now().replace(minute=5, second=0, microsecond=0)
        corrected = self.client_for(self.principal).patch(
            f'/api/attendance/presence/{presence.pk}/correct/',
            {'reason': 'Gate register correction', 'arrival_at': new_time.isoformat()},
            format='json',
        )
        self.assertEqual(corrected.status_code, 200, corrected.data)
        self.assertTrue(PlatformEvent.objects.filter(
            action='attendance.student_presence_corrected', target=f'presence:{presence.pk}'
        ).exists())


    def test_school_admin_can_promote_existing_staff_and_scope_class_teacher(self):
        teacher_user = User.objects.create_user(
            email='promote@batch21.test', password='Password!123', school=self.school,
            role='teacher', first_name='Promote', last_name='Me', must_change_password=False,
        )
        staff = StaffProfile.objects.create(
            user=teacher_user, school=self.school, employment_status='active'
        )
        arm_c = ClassArm.objects.create(
            school=self.school, class_level=self.level, name='C'
        )
        client = self.client_for(self.admin)

        promoted = client.patch(
            f'/api/staff/{staff.pk}/',
            {'new_role': 'class_teacher', 'assigned_classes': [arm_c.pk]},
            format='json',
        )
        self.assertEqual(promoted.status_code, 200, promoted.data)
        teacher_user.refresh_from_db()
        arm_c.refresh_from_db()
        self.assertEqual(teacher_user.role, 'class_teacher')
        self.assertEqual(arm_c.class_teacher_id, teacher_user.pk)

        principal = client.patch(
            f'/api/staff/{staff.pk}/',
            {'new_role': 'principal'},
            format='json',
        )
        self.assertEqual(principal.status_code, 200, principal.data)
        teacher_user.refresh_from_db()
        staff.refresh_from_db()
        arm_c.refresh_from_db()
        self.assertEqual(teacher_user.role, 'principal')
        self.assertIsNone(arm_c.class_teacher_id)
        self.assertEqual(staff.assigned_classes.count(), 0)
        self.assertTrue(PlatformEvent.objects.filter(
            action='school.staff_role_changed',
            target=str(staff.pk),
            details__after='principal',
        ).exists())
