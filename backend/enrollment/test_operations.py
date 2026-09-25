from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import CustomUser
from academics.models import AcademicSession, Term
from fees.billing import active_students
from gradebook.models import ScoreEntry
from tenants.models import School
from .models import ClassLevel, ClassArm, Subject, StaffProfile, StudentProfile, SubjectAssignment


class BasicOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name='Basic Academy', slug='basic-ops', subdomain='basic-ops', subscription_plan='basic')
        cls.other = School.objects.create(name='Other Academy', slug='other-ops', subdomain='other-ops', subscription_plan='basic')
        cls.admin = cls.user('admin', 'school_admin')
        cls.teacher = cls.user('teacher', 'teacher')
        cls.staff = StaffProfile.objects.create(school=cls.school, user=cls.teacher)
        cls.student = cls.user('student', 'student')
        cls.level = ClassLevel.objects.create(school=cls.school, name='JSS1')
        cls.arm = ClassArm.objects.create(school=cls.school, class_level=cls.level, name='A')
        cls.foreign_level = ClassLevel.objects.create(school=cls.other, name='JSS1')
        cls.profile = StudentProfile.objects.create(school=cls.school, user=cls.student, current_class=cls.arm)
        cls.subject = Subject.objects.create(school=cls.school, name='Math', code='MATH')
        cls.session = AcademicSession.objects.create(school=cls.school, name='2026/27', start_date=date(2026,9,1), end_date=date(2027,7,30))
        cls.term = Term.objects.create(session=cls.session, name='first', start_date=date(2026,9,1), end_date=date(2026,12,18))
        cls.assignment = SubjectAssignment.objects.create(school=cls.school, teacher=cls.staff, class_arm=cls.arm, subject=cls.subject, session=cls.session, term=cls.term)
        cls.score = ScoreEntry.objects.create(school=cls.school, student=cls.student, class_arm=cls.arm, subject=cls.subject, session=cls.session, term=cls.term, exam_score=50)

    @classmethod
    def user(cls, name, role):
        return CustomUser.objects.create_user(email=name+'@operations.test', password='Test-password-26!', role=role, school=cls.school, must_change_password=False)

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def test_foreign_class_and_subject_relationships_rejected(self):
        for url, data in [('/api/class-arms/', {'class_level':self.foreign_level.pk, 'name':'B'}),
                          ('/api/subjects/', {'name':'English', 'code':'ENG', 'class_levels':[self.foreign_level.pk]})]:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, data, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/class-arms/{self.arm.pk}/', {'class_level':self.foreign_level.pk}, format='json').status_code, 400)

    def test_foreign_calendar_assignment_rejected(self):
        session = AcademicSession.objects.create(school=self.other, name='2026/27', start_date=date(2026,9,1), end_date=date(2027,7,30))
        term = Term.objects.create(session=session, name='first', start_date=date(2026,9,1), end_date=date(2026,12,18))
        response = self.client.post('/api/subject-assignments/', {'teacher':self.staff.pk, 'class_arm':self.arm.pk,
            'subject':self.subject.pk, 'session':session.pk, 'term':term.pk}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(SubjectAssignment.objects.count(), 1)

    def test_bad_bulk_assignment_preserves_previous_assignments(self):
        response = self.client.post(f'/api/staff/{self.staff.pk}/assign-subjects/', {'session_id':self.session.pk,
            'term_id':self.term.pk, 'assignments':[{'subject_id':999999, 'class_arm_id':self.arm.pk}]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertTrue(SubjectAssignment.objects.filter(pk=self.assignment.pk).exists())

    def test_history_cannot_be_cascade_deleted(self):
        for path, pk in [('students',self.profile.pk), ('staff',self.staff.pk), ('subjects',self.subject.pk),
                         ('class-arms',self.arm.pk), ('class-levels',self.level.pk), ('terms',self.term.pk), ('sessions',self.session.pk)]:
            with self.subTest(path=path):
                self.assertEqual(self.client.delete(f'/api/{path}/{pk}/').status_code, 400)
        self.assertTrue(ScoreEntry.objects.filter(pk=self.score.pk).exists())

    def test_withdrawal_preserves_scores_and_excludes_billing(self):
        response = self.client.patch(f'/api/students/{self.profile.pk}/', {'status':'withdrawn'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(ScoreEntry.objects.filter(pk=self.score.pk).exists())
        self.assertEqual(active_students(self.school).count(), 0)

    def test_published_score_cannot_be_deleted(self):
        ScoreEntry.objects.filter(pk=self.score.pk).update(is_published=True)
        self.assertEqual(self.client.delete(f'/api/gradebook/entries/{self.score.pk}/').status_code, 400)
        self.assertTrue(ScoreEntry.objects.filter(pk=self.score.pk, is_published=True).exists())

    def test_teacher_cannot_change_another_subject(self):
        subject = Subject.objects.create(school=self.school, name='English', code='ENG')
        self.client.force_authenticate(self.teacher)
        response = self.client.post('/api/gradebook/entries/bulk-update/', {'class_arm':self.arm.pk,
            'subject':subject.pk, 'session':self.session.pk, 'term':self.term.pk,
            'scores':[{'student_id':self.student.pk, 'exam_score':40}]}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(ScoreEntry.objects.filter(subject=subject).exists())

    def test_class_sheet_includes_more_than_one_page_and_checks_assignment(self):
        for i in range(23):
            user = self.user('classmate'+str(i),'student')
            StudentProfile.objects.create(school=self.school,user=user,current_class=self.arm)
        self.client.force_authenticate(self.teacher)
        url = f'/api/gradebook/entries/sheet/?class_arm={self.arm.pk}&subject={self.subject.pk}&term={self.term.pk}'
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.data['students']),24)
        SubjectAssignment.objects.filter(pk=self.assignment.pk).delete()
        self.assertEqual(self.client.get(url).status_code,403)

    def test_basic_import_is_available_but_cbt_is_not(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        content = b'first_name,last_name,gender,dob,class_level,guardian_name,guardian_phone\nAda,Okafor,female,2012-01-01,JSS1,Parent,08000000000'
        response = self.client.post('/api/students/bulk-import/', {'file':SimpleUploadedFile('students.csv',content)}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['success_count'], 1, response.data)
        self.assertEqual(self.client.get('/api/cbt/exams/').status_code, 403)

    def test_setup_uses_only_current_school_data_and_protects_platform_fields(self):
        self.client.post(f'/api/sessions/{self.session.pk}/set-current/')
        self.client.post(f'/api/terms/{self.term.pk}/set-current/')
        response = self.client.get('/api/school/setup/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['missing_assignments'], 0)
        self.assertTrue(next(s['complete'] for s in response.data['steps'] if s['key']=='assignments'))
        self.assertEqual(self.client.patch('/api/school/setup/', {'name':'Updated Basic Academy','address':'School Road','phone':'08000000000'}, format='json').status_code, 200)
        self.assertEqual(self.client.patch('/api/school/setup/', {'subscription_plan':'enterprise'}, format='json').status_code, 400)
        other_admin = CustomUser.objects.create_user(email='other-admin@operations.test', password='test', role='school_admin', school=self.other)
        self.client.force_authenticate(other_admin)
        self.assertEqual(self.client.get('/api/school/setup/').status_code, 403)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get('/api/school/setup/').status_code, 403)

    def test_student_import_rejects_ambiguous_classes_and_duplicate_name_rows(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        ClassArm.objects.create(school=self.school, class_level=self.level, name='B')
        header = 'first_name,last_name,gender,dob,class_level,guardian_name,guardian_phone,class_arm\n'
        rows = ['Ada,Okafor,female,2012-01-01,JSS1,Parent,08000000000,',
                'Ada,Okafor,female,2012-01-01,JSS1,Parent,08000000000,A',
                'Ada,Okafor,female,2012-01-01,JSS1,Parent,08000000000,A']
        response = self.client.post('/api/students/bulk-import/', {'file':SimpleUploadedFile('students.csv',(header+'\n'.join(rows)).encode())}, format='multipart')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['success_count'], 1)
        self.assertEqual([error['row'] for error in response.data['errors']], [2,4])

    def test_staff_deactivation_retains_assignments_and_blocks_login(self):
        response = self.client.patch(f'/api/staff/{self.staff.pk}/', {'employment_status':'terminated'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.teacher.refresh_from_db()
        self.assertFalse(self.teacher.is_active)
        self.assertTrue(SubjectAssignment.objects.filter(pk=self.assignment.pk).exists())
        self.assertEqual(self.client.patch(f'/api/staff/{self.staff.pk}/', {'employment_status':'active'}, format='json').status_code, 200)
        self.teacher.refresh_from_db()
        self.assertTrue(self.teacher.is_active)

    def test_attendance_cannot_be_moved_and_excludes_withdrawn_from_finalization(self):
        from attendance.models import AttendanceSession
        withdrawn = self.user('withdrawn', 'student')
        StudentProfile.objects.create(user=withdrawn, school=self.school, current_class=self.arm, status='withdrawn')
        response = self.client.post('/api/attendance/sessions/start/', {'class_arm':self.arm.pk,'term':self.term.pk,'date':'2026-09-24','mode':'daily'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        pk = response.data['id']
        self.assertEqual(self.client.patch(f'/api/attendance/sessions/{pk}/', {'term':99999}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(f'/api/attendance/sessions/{pk}/finalize/', {}, format='json').status_code, 200)
        self.assertTrue(AttendanceSession.objects.get(pk=pk).is_finalized)

    def test_attendance_start_rejects_foreign_class_and_unassigned_teacher(self):
        foreign_arm = ClassArm.objects.create(school=self.other, class_level=self.foreign_level, name='A')
        payload = {'class_arm':foreign_arm.pk,'term':self.term.pk,'date':'2026-09-24','mode':'daily'}
        self.assertEqual(self.client.post('/api/attendance/sessions/start/',payload,format='json').status_code,400)
        arm = ClassArm.objects.create(school=self.school,class_level=self.level,name='B')
        self.client.force_authenticate(self.teacher)
        payload['class_arm'] = arm.pk
        self.assertEqual(self.client.post('/api/attendance/sessions/start/',payload,format='json').status_code,403)

    def test_explicit_parent_link_access_and_revocation(self):
        from accounts.models import ParentStudentLink
        payload = {'email':'parent@operations.test','phone':'08000000000','first_name':'Parent','last_name':'One','relationship':'guardian'}
        url = f'/api/students/{self.profile.pk}/parents/'
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 200)
        self.assertEqual(ParentStudentLink.objects.count(), 1)
        parent = CustomUser.objects.get(email=payload['email'])
        self.client.force_authenticate(parent)
        children = self.client.get('/api/parent/children/')
        self.assertEqual([child['student_id'] for child in children.data], [self.profile.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        unrelated = self.user('unrelated-parent', 'parent')
        self.client.force_authenticate(unrelated)
        self.assertEqual(self.client.get(f'/api/parent/dashboard/{self.profile.pk}/').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(url+'?link='+str(response.data['id'])).status_code, 204)
        self.client.force_authenticate(parent)
        self.assertEqual(self.client.get(f'/api/parent/dashboard/{self.profile.pk}/').status_code, 403)

    def test_foreign_parent_account_or_student_cannot_be_linked(self):
        foreign = CustomUser.objects.create_user(email='foreign-parent@operations.test',password='test',school=self.other,role='parent',phone_number='08000000000')
        payload = {'email':foreign.email,'phone':foreign.phone_number,'first_name':'Other','last_name':'Parent','relationship':'guardian'}
        response = self.client.post(f'/api/students/{self.profile.pk}/parents/',payload,format='json')
        self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(f'/api/students/{self.profile.pk}/parents/',payload,format='json').status_code, 403)

    def test_student_photo_targets_student_not_administrator(self):
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile
        with patch('tenants.image_uploads.store_uploaded_image',return_value='https://example.test/student.png'):
            response = self.client.post(f'/api/students/{self.profile.pk}/photo/',{'photo':SimpleUploadedFile('photo.png',b'validated-by-shared-uploader')},format='multipart')
        self.assertEqual(response.status_code,200)
        self.student.refresh_from_db();self.admin.refresh_from_db()
        self.assertEqual(self.student.profile_photo,'https://example.test/student.png')
        self.assertNotEqual(self.admin.profile_photo,self.student.profile_photo)

    def test_fresh_basic_school_default_term_journey(self):
        from fees.models import FeeSchedule
        school = School.objects.create(name='Journey Academy',slug='journey',subdomain='journey',subscription_plan='basic')
        admin = CustomUser.objects.create_user(email='journey-admin@test.invalid',password='Test-password-26!',role='school_admin',school=school,must_change_password=False)
        self.client = APIClient(HTTP_X_SCHOOL_SLUG='journey')
        self.client.force_authenticate(admin)
        def post(url, data, status=201):
            response = self.client.post(url,data,format='json')
            self.assertEqual(response.status_code,status,(url,response.data))
            return response.data
        self.assertEqual(self.client.patch('/api/school/setup/',{'address':'School Road','phone':'08011111111'},format='json').status_code,200)
        session = post('/api/sessions/',{'name':'2026/27','start_date':'2026-09-01','end_date':'2027-07-30'})
        term = post('/api/terms/',{'session':session['id'],'name':'first','start_date':'2026-09-01','end_date':'2026-12-18'})
        post(f"/api/sessions/{session['id']}/set-current/",{},200)
        post(f"/api/terms/{term['id']}/set-current/",{},200)
        level = post('/api/class-levels/',{'name':'JSS1'})
        arm = post('/api/class-arms/',{'name':'A','class_level':level['id']})
        subject = post('/api/subjects/',{'name':'Math','code':'MATH','class_levels':[level['id']]})
        staff = post('/api/staff/',{'new_email':'journey-teacher@test.invalid','new_first_name':'Ada','new_last_name':'Teacher','new_role':'teacher'})
        post('/api/subject-assignments/',{'teacher':staff['id'],'subject':subject['id'],'class_arm':arm['id'],'session':session['id'],'term':term['id']})
        student = post('/api/students/',{'new_first_name':'Ada','new_last_name':'Student','current_class':arm['id']})
        post(f"/api/students/{student['id']}/parents/",{'email':'journey-parent@test.invalid','first_name':'Parent','last_name':'One','phone':'08011111111','relationship':'guardian'})
        teacher = CustomUser.objects.get(pk=staff['user'])
        self.client.force_authenticate(teacher)
        password = 'New-classroom-password!26'
        post('/api/auth/change-password/',{'current_password':staff['staff_id'],'new_password':password,'confirm_password':password},200)
        teacher.refresh_from_db();self.client.force_authenticate(teacher)
        attendance = post('/api/attendance/sessions/start/',{'class_arm':arm['id'],'term':term['id'],'date':'2026-09-24','mode':'daily'})
        self.assertEqual(self.client.patch(f"/api/attendance/sessions/{attendance['id']}/submit/",{'records':[{'student_id':student['user'],'status':'late'}]},format='json').status_code,200)
        score_payload = {'class_arm':arm['id'],'subject':subject['id'],'term':term['id'],'session':session['id'],'scores':[{'student_id':student['user'],'first_test':10,'second_test':8,'assignment':8,'project':4,'practical':5,'exam_score':50}]}
        post('/api/gradebook/entries/bulk-update/',score_payload,200)
        self.assertEqual(ScoreEntry.objects.get(school=school).total_score,85)
        publish_url = f"/api/gradebook/entries/publish/?class_arm={arm['id']}&subject={subject['id']}&term={term['id']}"
        self.assertEqual(self.client.post(publish_url).status_code,403)
        self.client.force_authenticate(admin)
        post(publish_url.replace('/publish/','/submit/'),{},200)
        post(publish_url.replace('/publish/','/approve/'),{},200)
        post(publish_url,{},200)
        self.assertTrue(ScoreEntry.objects.get(school=school).is_published)
        category = post('/api/fees/categories/',{'name':'Tuition'})
        post('/api/fees/schedule/',{'term_id':term['id'],'schedules':[{'class_level_id':level['id'],'fee_category_id':category['id'],'amount':'10000.00'}]})
        schedule = FeeSchedule.objects.get(school=school)
        payment = post('/api/fees/pay/manual/',{'student_id':student['id'],'fee_schedule_id':schedule.pk,'amount_paid':'4000.00','payment_date':'2026-09-24','method':'bank_transfer'})
        parent = CustomUser.objects.get(email='journey-parent@test.invalid')
        self.client.force_authenticate(parent)
        slip = self.client.get(f"/api/results/slip-data/{student['user']}/?term={term['id']}")
        self.assertEqual(slip.status_code,200)
        summary = self.client.get(f"/api/fees/student/{student['id']}/?term={term['id']}")
        self.assertEqual(summary.status_code,200)
        self.assertEqual(summary.data[0]['outstanding'],6000)
        receipt = self.client.get(f"/api/fees/receipts/{payment['id']}/")
        self.assertEqual(receipt.status_code,200)
        self.assertTrue(receipt.content.startswith(b'%PDF'))
        self.assertEqual(self.client.get(f'/api/fees/student/{self.profile.pk}/').status_code,404)
