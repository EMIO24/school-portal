from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from accounts.models import CustomUser, ParentStudentLink
from tenants.models import PlatformEvent
from gradebook.models import ScoreEntry
from . import test_operations as operations
from .models import StudentProfile, StaffProfile


class BasicCompletionTests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)
    setUp = operations.BasicOperationsTests.setUp

    def test_student_identity_edit_preserves_account_password_and_published_history(self):
        ScoreEntry.objects.filter(pk=self.score.pk).update(is_published=True)
        before=(self.student.pk,self.student.password,self.profile.admission_number,self.score.total_score,self.score.grade)
        response=self.client.patch(f'/api/students/{self.profile.pk}/',{'new_first_name':'Corrected','new_last_name':'Student','new_email':'CORRECTED@example.test'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.student.refresh_from_db();self.profile.refresh_from_db();self.score.refresh_from_db()
        self.assertEqual(self.student.first_name,'Corrected');self.assertEqual(self.student.email,'corrected@example.test')
        self.assertEqual(before,(self.student.pk,self.student.password,self.profile.admission_number,self.score.total_score,self.score.grade))
        self.assertTrue(self.score.is_published)
        self.assertTrue(PlatformEvent.objects.filter(action='school.account_updated',target=str(self.student.pk)).exists())

    def test_staff_identity_and_activation_preserve_assignments(self):
        password=self.teacher.password
        response=self.client.patch(f'/api/staff/{self.staff.pk}/',{'new_first_name':'Corrected','new_email':'teacher-new@example.test','employment_status':'suspended','new_role':'school_admin'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.teacher.refresh_from_db();self.assertFalse(self.teacher.is_active)
        self.assertEqual(self.teacher.role,'teacher');self.assertEqual(self.teacher.password,password)
        self.assertEqual(self.teacher.first_name,'Corrected');self.assignment.refresh_from_db()
        self.assertEqual(self.client.patch(f'/api/staff/{self.staff.pk}/',{'employment_status':'active'},format='json').status_code,200)
        self.teacher.refresh_from_db();self.assertTrue(self.teacher.is_active)
        response=self.client.post('/api/staff/',{'new_first_name':'Leave','new_last_name':'Teacher','new_email':'leave@example.test','employment_status':'on_leave'},format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertTrue(CustomUser.objects.get(email='leave@example.test').is_active)

    def test_email_collision_rolls_back_profile_and_identity_changes(self):
        foreign=CustomUser.objects.create_user(email='occupied@example.test',school=self.other,role='teacher')
        for path,pk in [('students',self.profile.pk),('staff',self.staff.pk)]:
            response=self.client.patch(f'/api/{path}/{pk}/',{'new_email':foreign.email.upper(),'new_first_name':'Not saved','gender':'female'},format='json')
            self.assertEqual(response.status_code,400,response.data)
            self.assertNotIn(self.other.name,str(response.data))
        self.student.refresh_from_db();self.teacher.refresh_from_db()
        self.assertNotEqual(self.student.first_name,'Not saved');self.assertNotEqual(self.teacher.first_name,'Not saved')
        for path in ['students','staff']:
            response=self.client.post(f'/api/{path}/',{'new_email':foreign.email.upper(),'new_first_name':'Duplicate','new_last_name':'Account'},format='json')
            self.assertEqual(response.status_code,400,response.data)

    def test_student_deactivation_and_reactivation_preserve_history(self):
        from fees.models import FeeCategory, FeeSchedule, FeePayment
        from attendance.models import AttendanceSession, AttendanceRecord
        category=FeeCategory.objects.create(school=self.school,name='Tuition')
        schedule=FeeSchedule.objects.create(school=self.school,term=self.term,class_level=self.level,fee_category=category,amount=10000)
        payment=FeePayment.objects.create(school=self.school,student=self.profile,fee_schedule=schedule,amount_paid=4000,payment_date=self.term.start_date,method='cash',recorded_by=self.admin)
        register=AttendanceSession.objects.create(school=self.school,class_arm=self.arm,teacher=self.teacher,term=self.term,date=self.term.start_date)
        attendance=AttendanceRecord.objects.create(attendance_session=register,student=self.student,status='present')
        for state,active in [('withdrawn',False),('active',True)]:
            response=self.client.patch(f'/api/students/{self.profile.pk}/',{'status':state},format='json')
            self.assertEqual(response.status_code,200,response.data)
            self.student.refresh_from_db();self.assertEqual(self.student.is_active,active)
            self.assertTrue(ScoreEntry.objects.filter(pk=self.score.pk).exists())
            payment.refresh_from_db();attendance.refresh_from_db()
            self.assertEqual(payment.amount_paid,4000);self.assertEqual(attendance.status,'present')

    def test_foreign_profile_edit_and_deactivation_rejected(self):
        foreign=CustomUser.objects.create_user(email='other-student@example.test',role='student',school=self.other)
        profile=StudentProfile.objects.create(school=self.other,user=foreign)
        teacher=CustomUser.objects.create_user(email='other-teacher@example.test',role='teacher',school=self.other)
        staff=StaffProfile.objects.create(school=self.other,user=teacher)
        for path,pk,data in [('students',profile.pk,{'new_first_name':'Hacked','status':'withdrawn'}),('staff',staff.pk,{'employment_status':'suspended'})]:
            self.assertEqual(self.client.patch(f'/api/{path}/{pk}/',data,format='json').status_code,404)
        foreign.refresh_from_db();teacher.refresh_from_db();self.assertTrue(foreign.is_active and teacher.is_active)

    def test_teacher_cannot_edit_accounts_or_manipulate_parent_links(self):
        self.client.force_authenticate(self.teacher)
        for path in [f'/api/students/{self.profile.pk}/',f'/api/staff/{self.staff.pk}/',f'/api/students/{self.profile.pk}/parents/?link=1']:
            self.assertEqual(self.client.patch(path,{'new_first_name':'Hacked'},format='json').status_code,403)

    def parent_data(self):
        return {'first_name':'Parent','last_name':'One','email':'parent@completion.test','phone':'08012345678','relationship':'guardian'}

    def test_parent_reuse_edit_search_and_unlink(self):
        data=self.parent_data();url=f'/api/students/{self.profile.pk}/parents/'
        response=self.client.post(url,data,format='json');self.assertEqual(response.status_code,201,response.data)
        link=response.data['id'];parent=CustomUser.objects.get(email=data['email'])
        child=self.user('child-two','student');profile=StudentProfile.objects.create(school=self.school,user=child,current_class=self.arm)
        self.assertEqual(self.client.post(f'/api/students/{profile.pk}/parents/',data,format='json').status_code,201)
        self.assertEqual(CustomUser.objects.filter(school=self.school,role='parent').count(),1)
        self.assertEqual(len(self.client.get(url,{'search':'Parent'}).data),1)
        self.assertEqual(self.client.patch(url+f'?link={link}',{'first_name':'Corrected','phone':'08012345679'},format='json').status_code,200)
        parent.refresh_from_db();self.assertEqual(parent.first_name,'Corrected')
        ScoreEntry.objects.filter(pk=self.score.pk).update(is_published=True)
        self.client.force_authenticate(parent)
        self.assertEqual(self.client.get(f'/api/results/slip-data/{self.student.pk}/?term={self.term.pk}').status_code,200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(url+f'?link={link}').status_code,204)
        self.client.force_authenticate(parent)
        self.assertEqual(self.client.get(f'/api/results/slip-data/{self.student.pk}/?term={self.term.pk}').status_code,403)
        self.assertEqual(ParentStudentLink.objects.filter(parent=parent,student=profile).count(),1)
        self.assertTrue(ScoreEntry.objects.filter(pk=self.score.pk).exists())

    def test_foreign_parent_and_links_cannot_be_used_or_searched(self):
        data=self.parent_data();parent=CustomUser.objects.create_user(email=data['email'],school=self.other,role='parent',phone_number=data['phone'])
        child=CustomUser.objects.create_user(role='student',school=self.other)
        profile=StudentProfile.objects.create(school=self.other,user=child)
        link=ParentStudentLink.objects.create(school=self.other,parent=parent,student=profile)
        url=f'/api/students/{self.profile.pk}/parents/'
        self.assertEqual(self.client.post(url,data,format='json').status_code,400)
        self.assertEqual(self.client.get(url,{'search':'parent'}).data,[])
        self.assertEqual(self.client.patch(url+f'?link={link.pk}',{'first_name':'Hacked'},format='json').status_code,404)
        self.assertEqual(self.client.delete(url+f'?link={link.pk}').status_code,404)

    def upload(self,kind,text):
        return self.client.post(f'/api/{kind}/bulk-import/',{'file':SimpleUploadedFile('import.csv',text.encode())},format='multipart')

    def test_student_import_partial_failures_and_repeated_rows(self):
        header='first_name,last_name,gender,dob,class_level,guardian_name,guardian_phone\n'
        row='Ada,New,female,2012-01-01,JSS1,Parent,08012345678'
        response=self.upload('students',header+row+'\n'+row+'\nBad,Row,male,invalid,JSS1,Parent,08012345678')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['success_count'],1);self.assertEqual(response.data['error_count'],2)
        self.assertEqual([e['row'] for e in response.data['errors']],[3,4])
        self.assertEqual(self.upload('students',header+row).data['success_count'],0)

    def test_import_identifiers_are_rejected_instead_of_silently_ignored(self):
        for field in ['admission_number','student_id','school_id']:
            response=self.upload('students',f'first_name,last_name,gender,dob,class_level,guardian_name,guardian_phone,{field}\nAda,New,female,2012-01-01,JSS1,Parent,08012345678,{self.profile.admission_number}')
            self.assertEqual(response.status_code,400)
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(),1)

    def test_staff_import_rejects_invalid_email_duplicate_headers_and_short_rows(self):
        response=self.upload('staff','first_name,last_name,email,role\nAda,New,not-email,teacher\nShort,row')
        self.assertEqual(response.data['success_count'],0);self.assertEqual(response.data['error_count'],2)
        self.assertEqual(self.upload('staff','first_name,last_name,email,role,email\nA,B,a@b.test,teacher,a@b.test').status_code,400)

    def test_private_selectors_and_search_are_tenant_scoped(self):
        foreign=CustomUser.objects.create_user(email='secret@other.test',school=self.other,role='student')
        StudentProfile.objects.create(school=self.other,user=foreign)
        self.assertEqual(self.client.get('/api/students/?search=secret').data['count'],0)
        self.client.force_authenticate(self.teacher)
        response=self.client.get('/api/subject-assignments/?mine=true')
        self.assertEqual(response.status_code,200);self.assertEqual(response.data['count'],1)
        self.assertEqual(self.client.get(f'/api/subject-assignments/?mine=true&teacher={999999}').data['count'],0)

    def test_student_directory_query_count_stays_bounded_at_500_students(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        self.client.get('/api/students/')
        with CaptureQueriesContext(connection) as initial:
            self.client.get('/api/students/')
        users=CustomUser.objects.bulk_create([CustomUser(school=self.school,role='student',first_name='Student',last_name=str(i)) for i in range(499)])
        StudentProfile.objects.bulk_create([StudentProfile(school=self.school,user=u,admission_number=f'PERF-{i}',current_class=self.arm) for i,u in enumerate(users)])
        with CaptureQueriesContext(connection) as measured:
            response=self.client.get('/api/students/')
        self.assertEqual(response.data['count'],500)
        self.assertLessEqual(len(response.data['results']),20)
        self.assertLessEqual(len(measured),len(initial)+1)
        print(f'Basic student directory: 500 records, {len(response.data["results"])} returned, {len(initial)} baseline / {len(measured)} measured SQL queries (SQLite).')
