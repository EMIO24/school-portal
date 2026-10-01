import time
from io import BytesIO
from datetime import date

from openpyxl import Workbook

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import CustomUser, ParentStudentLink
from academics.models import AcademicSession, Term
from tenants.models import PlatformEvent, School
from timetable.models import Period, TimetableEntry
from fees.models import FeeCategory, FeeSchedule
from curriculum.models import CurriculumSource, CurriculumVersion, SchoolAcademicStandard, AcademicStandardTopic
from .models import (ClassArm, ClassLevel, MigrationConflict, MigrationJob, MigrationMappingProfile,
                     MigrationStudentReference, SessionEnrollment, StaffProfile, StudentProfile,
                     Subject, SubjectAssignment)


class MigrationCentreTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='Migration School', slug='migration-school', subdomain='migration-school')
        self.other = School.objects.create(name='Other School', slug='migration-other', subdomain='migration-other')
        self.admin = CustomUser.objects.create_user(email='admin@migration.test', password='test',
            school=self.school, role='school_admin', must_change_password=False)
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def upload(self, domain, operation, body, mapping=None):
        from json import dumps
        return self.client.post(f'/api/migration/{domain}/{operation}/', {
            'file': SimpleUploadedFile('school.csv', body.encode(), content_type='text/csv'),
            'mapping': dumps(mapping or {}),
        }, format='multipart')

    def test_templates_mapping_and_file_security(self):
        template = self.client.get('/api/migration/templates/students/')
        self.assertEqual(template.status_code, 200)
        self.assertIn(b'student_ref', template.content)
        self.assertNotIn(b'password', template.content)
        data = 'Class Level,Class Arm\nJSS1,A'
        preview = self.upload('classes', 'validate', data)
        self.assertEqual(preview.data['counts']['CREATE'], 1)
        self.assertFalse(ClassArm.objects.exists())
        mapped = self.upload('classes', 'validate', 'Level Name,Arm Name,Legacy Note\nJSS1,A,old school',
                             {'Level Name':'class_level','Arm Name':'class_arm'})
        self.assertEqual(mapped.data['counts']['CREATE'], 1)
        self.assertEqual(mapped.data['warnings'], ['Ignored column: Legacy Note'])
        self.assertEqual(self.upload('classes', 'validate', data, {'Class Level':None}).status_code, 400)
        self.assertEqual(self.upload('classes', 'validate', 'class_level,class_level\nJSS1,JSS1').status_code, 400)
        self.assertEqual(self.upload('classes', 'validate', 'Class Level,class_level,class_arm\nJSS1,JSS1,A').status_code, 400)
        self.assertEqual(self.upload('classes', 'validate', 'school_id,class_level,class_arm\n1,JSS1,A').status_code, 400)
        self.assertEqual(self.upload('classes', 'validate', 'password_hash,class_level,class_arm\nx,JSS1,A').status_code, 400)
        self.assertEqual(self.upload('classes', 'validate', data, {'Class Level':'class_arm','Class Arm':'class_arm'}).status_code, 400)
        self.assertEqual(self.upload('classes', 'validate', 'class_level,class_arm\nJSS1').data['counts']['REJECT'], 1)
        self.assertEqual(self.upload('classes', 'validate', 'class_level,class_arm\nJSS1,=1+1').data['counts']['REJECT'], 1)
        teacher = CustomUser.objects.create_user(email='teacher@migration.test', password='test', school=self.school, role='teacher')
        self.client.force_authenticate(teacher)
        self.assertEqual(self.upload('classes', 'import', data).status_code, 403)
        self.assertEqual(self.client.get('/api/migration/').status_code, 403)

    def test_excel_inspect_validate_import_and_formula_rejection(self):
        def workbook_file(rows):
            stream = BytesIO()
            book = Workbook()
            sheet = book.active
            for row in rows:
                sheet.append(row)
            book.save(stream)
            return SimpleUploadedFile(
                'school.xlsx', stream.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        inspect = self.client.post('/api/migration/classes/inspect/', {
            'file': workbook_file([
                ['Class Level', 'Class Arm', 'Legacy Note'],
                ['JSS1', 'A', 'old spreadsheet'],
            ]),
        }, format='multipart')
        self.assertEqual(inspect.status_code, 200, inspect.data)
        self.assertEqual(inspect.data['format'], 'xlsx')
        self.assertEqual(inspect.data['total_rows'], 1)
        self.assertEqual(inspect.data['suggested_mapping']['Class Level'], 'class_level')
        self.assertEqual(inspect.data['suggested_mapping']['Class Arm'], 'class_arm')

        mapping = '{"Class Level":"class_level","Class Arm":"class_arm"}'
        validate = self.client.post('/api/migration/classes/validate/', {
            'file': workbook_file([
                ['Class Level', 'Class Arm', 'Legacy Note'],
                ['JSS1', 'A', 'old spreadsheet'],
            ]),
            'mapping': mapping,
        }, format='multipart')
        self.assertEqual(validate.data['counts'], {'CREATE': 1, 'REUSE': 0, 'REJECT': 0})
        self.assertEqual(validate.data['warnings'], ['Ignored column: Legacy Note'])
        self.assertFalse(ClassArm.objects.exists())

        imported = self.client.post('/api/migration/classes/import/', {
            'file': workbook_file([
                ['Class Level', 'Class Arm', 'Legacy Note'],
                ['JSS1', 'A', 'old spreadsheet'],
            ]),
            'mapping': mapping,
        }, format='multipart')
        self.assertEqual(imported.data['counts']['CREATE'], 1)
        self.assertEqual(ClassArm.objects.get(school=self.school).full_name, 'JSS1A')

        formula = self.client.post('/api/migration/classes/validate/', {
            'file': workbook_file([
                ['class_level', 'class_arm'],
                ['JSS2', '=1+1'],
            ]),
            'mapping': '{}',
        }, format='multipart')
        self.assertEqual(formula.data['counts']['REJECT'], 1)
        self.assertEqual(formula.data['rows'][0]['field'], 'file')

    def test_operational_sequence_retries_and_readiness(self):
        session = AcademicSession.objects.create(school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 1), is_current=True)
        Term.objects.create(session=session, name='first', start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15), is_current=True)
        files = [
            ('classes', 'class_level,class_arm\nJSS1,A'),
            ('subjects', 'code,name,class_level\nMATH,Mathematics,JSS1'),
            ('students', 'student_ref,first_name,last_name,class_level,class_arm,email,dob\nOLD-1,Ada,Okafor,JSS1,A,ada@migration.test,2013-01-02'),
            ('staff', 'first_name,last_name,email\nTayo,Teacher,tayo@migration.test'),
            ('parents', 'first_name,last_name,email,phone\nParent,One,parent@migration.test,08012345678'),
            ('parent_links', 'parent_email,student_ref,relationship\nparent@migration.test,OLD-1,mother'),
            ('assignments', 'teacher_email,class_level,class_arm,subject_code\ntayo@migration.test,JSS1,A,MATH'),
        ]
        for domain, body in files:
            with self.subTest(domain=domain):
                preview = self.upload(domain, 'validate', body)
                self.assertEqual(preview.status_code, 200, preview.data)
                self.assertEqual(preview.data['counts'], {'CREATE': 1, 'REUSE': 0, 'REJECT': 0})
                imported = self.upload(domain, 'import', body)
                self.assertEqual(imported.status_code, 200, imported.data)
                self.assertEqual(imported.data['counts']['CREATE'], 1)
                retry = self.upload(domain, 'import', body)
                self.assertEqual(retry.data['counts'], {'CREATE': 0, 'REUSE': 1, 'REJECT': 0})
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(), 1)
        self.assertEqual(StaffProfile.objects.filter(school=self.school).count(), 1)
        self.assertEqual(ParentStudentLink.objects.filter(school=self.school).count(), 1)
        self.assertEqual(SubjectAssignment.objects.filter(school=self.school).count(), 1)
        student = StudentProfile.objects.get(school=self.school)
        self.assertTrue(student.user.must_change_password)
        self.assertTrue(student.user.check_password(student.admission_number))
        staff = StaffProfile.objects.get(school=self.school)
        self.assertTrue(staff.user.check_password(staff.staff_id))
        parent = CustomUser.objects.get(email='parent@migration.test')
        self.assertFalse(parent.has_usable_password())
        self.assertEqual(MigrationStudentReference.objects.get(student=student).reference, 'OLD-1')
        self.assertEqual(PlatformEvent.objects.filter(action='school.migration_completed').count(), 7)
        readiness = self.client.get('/api/school/setup/').data['steps']
        for key in ('classes', 'subjects', 'teachers', 'assignments'):
            self.assertTrue(next(step for step in readiness if step['key'] == key)['complete'])

    def test_partial_errors_and_cross_tenant_references(self):
        AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 1),
            is_current=True,
        )
        self.upload('classes', 'import', 'class_level,class_arm\nJSS1,A')
        csv = ('student_ref,first_name,last_name,class_level,class_arm,dob\n'
               'ONE,Ada,One,JSS1,A,2013-01-02\nTWO,Bad,Date,JSS1,A,not-a-date\n'
               'ONE,Ada,One,JSS1,A,2013-01-02')
        preview = self.upload('students', 'validate', csv)
        self.assertEqual(preview.data['counts'], {'CREATE': 1, 'REUSE': 0, 'REJECT': 2})
        self.assertEqual(StudentProfile.objects.count(), 0)
        imported = self.upload('students', 'import', csv)
        self.assertEqual(imported.data['counts'], {'CREATE': 1, 'REUSE': 0, 'REJECT': 2})
        self.assertEqual(StudentProfile.objects.count(), 1)
        foreign_parent = CustomUser.objects.create_user(email='foreign@migration.test', password=None,
            school=self.other, role='parent', phone_number='08000000000')
        foreign_level = ClassLevel.objects.create(school=self.other, name='SS1')
        foreign_arm = ClassArm.objects.create(school=self.other, class_level=foreign_level, name='A')
        foreign_user = CustomUser.objects.create_user(email=None, password='test',
            school=self.other, role='student', first_name='Foreign', last_name='Student')
        foreign_student = StudentProfile.objects.create(school=self.other, user=foreign_user, current_class=foreign_arm)
        MigrationStudentReference.objects.create(school=self.other, reference='FOREIGN', student=foreign_student)
        foreign_teacher = CustomUser.objects.create_user(email='foreign-teacher@migration.test', password='test',
            school=self.other, role='teacher')
        StaffProfile.objects.create(school=self.other, user=foreign_teacher)
        self.assertEqual(self.upload('parent_links', 'validate',
            'parent_email,student_ref,relationship\nforeign@migration.test,ONE,mother').data['counts']['REJECT'], 1)
        self.upload('parents', 'import', 'first_name,last_name,email,phone\nParent,One,local@migration.test,08012345678')
        self.assertEqual(self.upload('parent_links', 'validate',
            'parent_email,student_ref,relationship\nlocal@migration.test,FOREIGN,mother').data['counts']['REJECT'], 1)
        self.assertEqual(ParentStudentLink.objects.count(), 0)
        self.assertEqual(foreign_parent.school, self.other)
        self.assertEqual(self.upload('assignments', 'validate',
            'teacher_email,class_level,class_arm,subject_code\nforeign-teacher@migration.test,JSS1,A,MATH').data['counts']['REJECT'], 1)
        self.assertEqual(self.upload('students', 'validate',
            'student_ref,first_name,last_name,class_level,class_arm\nOTHER,Ada,Other,SS1,A').data['counts']['REJECT'], 1)
        other_admin = CustomUser.objects.create_user(email='admin@other-migration.test', password='test',
            school=self.other, role='school_admin')
        self.client.force_authenticate(other_admin)
        self.assertEqual(self.upload('classes', 'import', 'class_level,class_arm\nJSS1,B').status_code, 403)

    def test_existing_student_admission_number_can_be_linked_without_source_ids(self):
        student_user = CustomUser.objects.create_user(email=None, password='test', school=self.school,
            role='student', first_name='Existing', last_name='Student')
        student = StudentProfile.objects.create(school=self.school, user=student_user)
        self.upload('parents', 'import', 'first_name,last_name,email,phone\nParent,One,local@migration.test,08012345678')
        response = self.upload('parent_links', 'import',
            f'parent_email,student_ref,relationship\nlocal@migration.test,{student.admission_number},guardian')
        self.assertEqual(response.data['counts']['CREATE'], 1)

    def test_subject_coverage_and_guardian_contact_do_not_grant_access(self):
        AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 1),
            is_current=True,
        )
        self.upload('classes', 'import', 'class_level,class_arm\nJSS1,A\nJSS2,A')
        response = self.upload('subjects', 'import', 'code,name,class_levels\nMATH,Mathematics,JSS1;JSS2')
        self.assertEqual(response.data['counts']['CREATE'], 1)
        self.assertEqual(Subject.objects.get(school=self.school, code='MATH').class_levels.count(), 2)
        student_csv = ('student_ref,first_name,last_name,class_level,class_arm,guardian_name,guardian_phone,guardian_email\n'
                       'OLD-1,Ada,Okafor,JSS1,A,Parent One,08012345678,parent@migration.test')
        self.assertEqual(self.upload('students', 'import', student_csv).data['counts']['CREATE'], 1)
        self.assertEqual(ParentStudentLink.objects.count(), 0)
        self.assertFalse(CustomUser.objects.filter(email='parent@migration.test').exists())
        changed = student_csv.replace('Ada,Okafor', 'Other,Student')
        self.assertEqual(self.upload('students', 'validate', changed).data['counts']['REJECT'], 1)
        duplicate_email = ('student_ref,first_name,last_name,class_level,class_arm,email\n'
                           'R1,One,Student,JSS1,A,same@migration.test\n'
                           'R2,Two,Student,JSS1,A,same@migration.test')
        self.assertEqual(self.upload('students', 'validate', duplicate_email).data['counts']['REJECT'], 1)

    def test_dry_run_rejects_in_file_parent_phone_and_assignment_conflicts(self):
        parents = ('first_name,last_name,email,phone\n'
                   'First,Parent,first@migration.test,08012345678\n'
                   'Second,Parent,second@migration.test,08012345678')
        self.assertEqual(self.upload('parents', 'validate', parents).data['counts'],
                         {'CREATE': 1, 'REUSE': 0, 'REJECT': 1})
        self.upload('classes', 'import', 'class_level,class_arm\nJSS1,A')
        self.upload('subjects', 'import', 'code,name,class_level\nMATH,Mathematics,JSS1')
        self.upload('staff', 'import', 'first_name,last_name,email\nOne,Teacher,one@migration.test\nTwo,Teacher,two@migration.test')
        session = AcademicSession.objects.create(school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 1), is_current=True)
        Term.objects.create(session=session, name='first', start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15), is_current=True)
        assignments = ('teacher_email,class_level,class_arm,subject_code\n'
                       'one@migration.test,JSS1,A,MATH\n'
                       'two@migration.test,JSS1,A,MATH')
        self.assertEqual(self.upload('assignments', 'validate', assignments).data['counts'],
                         {'CREATE': 1, 'REUSE': 0, 'REJECT': 1})



    def test_high_volume_operational_imports_are_validated_and_retry_safe(self):
        session = AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 1), is_current=True
        )
        term = Term.objects.create(
            session=session, name='first', start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15), is_current=True
        )
        self.upload('classes', 'import', 'class_level,class_arm\nJSS1,A')
        self.upload('subjects', 'import', 'code,name,class_level\nMATH,Mathematics,JSS1')
        self.upload('staff', 'import', 'first_name,last_name,email\nTayo,Teacher,tayo@migration.test')
        self.upload('assignments', 'import',
                    'teacher_email,class_level,class_arm,subject_code\ntayo@migration.test,JSS1,A,MATH')
        Period.objects.create(
            school=self.school, name='Period 1', start_time='08:00',
            end_time='08:40', order_index=1
        )

        timetable_csv = (
            'class_level,class_arm,subject_code,teacher_email,day,period\n'
            'JSS1,A,MATH,tayo@migration.test,Monday,1'
        )
        preview = self.upload('timetable', 'validate', timetable_csv)
        self.assertEqual(preview.data['counts'], {'CREATE': 1, 'REUSE': 0, 'REJECT': 0})
        self.assertEqual(TimetableEntry.objects.count(), 0)
        imported = self.upload('timetable', 'import', timetable_csv)
        self.assertEqual(imported.data['counts']['CREATE'], 1)
        self.assertEqual(self.upload('timetable', 'import', timetable_csv).data['counts']['REUSE'], 1)

        category = FeeCategory.objects.create(school=self.school, name='Tuition')
        fee_csv = 'class_level,fee_category,amount,due_date\nJSS1,Tuition,75000.00,2026-10-31'
        preview = self.upload('fee_schedules', 'validate', fee_csv)
        self.assertEqual(preview.data['counts']['CREATE'], 1)
        self.assertEqual(FeeSchedule.objects.count(), 0)
        imported = self.upload('fee_schedules', 'import', fee_csv)
        self.assertEqual(imported.data['counts']['CREATE'], 1)
        self.assertEqual(FeeSchedule.objects.get(fee_category=category, term=term).amount, 75000)
        self.assertEqual(self.upload('fee_schedules', 'import', fee_csv).data['counts']['REUSE'], 1)
        changed_fee = fee_csv.replace('75000.00', '80000.00')
        self.assertEqual(self.upload('fee_schedules', 'validate', changed_fee).data['counts']['REJECT'], 1)

        level = ClassLevel.objects.get(school=self.school, name='JSS1')
        subject = Subject.objects.get(school=self.school, code='MATH')
        source = CurriculumSource.objects.create(school=self.school, name='Recorded Source', kind='other')
        version = CurriculumVersion.objects.create(source=source, label='2026')
        standard = SchoolAcademicStandard.objects.create(
            school=self.school, curriculum_version=version, class_level=level,
            subject=subject, title='JSS1 Mathematics Standard', created_by=self.admin
        )
        topic_csv = (
            'standard_title,class_level,subject_code,term,position,title,recommended_week,requirement,objectives\n'
            'JSS1 Mathematics Standard,JSS1,MATH,first,1,Whole Numbers,1,required,Define whole numbers;Compare whole numbers'
        )
        preview = self.upload('standard_topics', 'validate', topic_csv)
        self.assertEqual(preview.data['counts']['CREATE'], 1)
        self.assertEqual(AcademicStandardTopic.objects.count(), 0)
        imported = self.upload('standard_topics', 'import', topic_csv)
        self.assertEqual(imported.data['counts']['CREATE'], 1)
        topic = AcademicStandardTopic.objects.get(standard=standard, position=1)
        self.assertEqual(topic.objectives.count(), 2)
        self.assertEqual(self.upload('standard_topics', 'import', topic_csv).data['counts']['REUSE'], 1)
        standard.status = SchoolAcademicStandard.Status.APPROVED
        standard.save(update_fields=['status'])
        second_topic = topic_csv.replace(',1,Whole Numbers,1,', ',2,Fractions,2,')
        self.assertEqual(self.upload('standard_topics', 'validate', second_topic).data['counts']['REJECT'], 1)

    def test_timetable_import_rejects_same_file_teacher_double_booking(self):
        session = AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 1), is_current=True
        )
        Term.objects.create(
            session=session, name='first', start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15), is_current=True
        )
        self.upload('classes', 'import', 'class_level,class_arm\nJSS1,A\nJSS1,B')
        self.upload('subjects', 'import', 'code,name,class_level\nMATH,Mathematics,JSS1')
        self.upload('staff', 'import', 'first_name,last_name,email\nTayo,Teacher,tayo@migration.test')
        self.upload('assignments', 'import',
                    'teacher_email,class_level,class_arm,subject_code\n'
                    'tayo@migration.test,JSS1,A,MATH\n'
                    'tayo@migration.test,JSS1,B,MATH')
        Period.objects.create(
            school=self.school, name='Period 1', start_time='08:00',
            end_time='08:40', order_index=1
        )
        csv = (
            'class_level,class_arm,subject_code,teacher_email,day,period\n'
            'JSS1,A,MATH,tayo@migration.test,MON,1\n'
            'JSS1,B,MATH,tayo@migration.test,MON,1'
        )
        response = self.upload('timetable', 'validate', csv)
        self.assertEqual(response.data['counts'], {'CREATE': 1, 'REUSE': 0, 'REJECT': 1})
        self.assertEqual(TimetableEntry.objects.count(), 0)

    @override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
    def test_400_student_simulation_is_retry_safe(self):
        session = AcademicSession.objects.create(school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 1), is_current=True)
        Term.objects.create(session=session, name='first', start_date=date(2026, 9, 1),
            end_date=date(2026, 12, 15), is_current=True)
        arms = [chr(65 + i) for i in range(20)]
        classes = 'class_level,class_arm\n' + ''.join(f'JSS1,{arm}\n' for arm in arms)
        self.assertEqual(self.upload('classes', 'import', classes).data['counts']['CREATE'], 20)
        subjects = 'code,name,class_level\n' + ''.join(f'SUB{i},Subject{i},JSS1\n' for i in range(15))
        self.assertEqual(self.upload('subjects', 'import', subjects).data['counts']['CREATE'], 15)
        header = 'student_ref,first_name,last_name,class_level,class_arm,dob\n'
        body = header + ''.join(f'OLD-{i},Student,Number{i},JSS1,{arms[i % 20]},2013-01-02\n' for i in range(400))
        started = time.perf_counter()
        preview = self.upload('students', 'validate', body)
        self.assertEqual(preview.data['counts']['CREATE'], 400)
        self.assertEqual(StudentProfile.objects.count(), 0)
        imported = self.upload('students', 'import', body)
        self.assertEqual(imported.data['counts']['CREATE'], 400)
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(), 400)
        retry = self.upload('students', 'import', body)
        self.assertEqual(retry.data['counts']['REUSE'], 400)
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(), 400)
        staff = 'first_name,last_name,email\n' + ''.join(
            f'Teacher,Number{i},teacher{i}@migration.test\n' for i in range(40))
        self.assertEqual(self.upload('staff', 'import', staff).data['counts']['CREATE'], 40)
        parents = 'first_name,last_name,email,phone\n' + ''.join(
            f'Parent,Number{i},parent{i}@migration.test,0801234{i:04d}\n' for i in range(40))
        self.assertEqual(self.upload('parents', 'import', parents).data['counts']['CREATE'], 40)
        links = 'parent_email,student_ref,relationship\n' + ''.join(
            f'parent{i}@migration.test,OLD-{i},guardian\n' for i in range(40))
        self.assertEqual(self.upload('parent_links', 'import', links).data['counts']['CREATE'], 40)
        assignments = 'teacher_email,class_level,class_arm,subject_code\n' + ''.join(
            f'teacher{i}@migration.test,JSS1,{arms[i]},SUB{i % 15}\n' for i in range(20))
        self.assertEqual(self.upload('assignments', 'import', assignments).data['counts']['CREATE'], 20)
        self.assertEqual(ParentStudentLink.objects.filter(school=self.school).count(), 40)
        self.assertEqual(SubjectAssignment.objects.filter(school=self.school).count(), 20)
        print(f'MIGRATION_SIMULATION_SQLITE students=400 teachers=40 parents=40 arms=20 subjects=15 assignments=20 total_seconds={time.perf_counter()-started:.2f}')


    def test_batch20_exact_file_replay_keeps_one_provenance_job(self):
        body = 'class_level,class_arm\nJSS1,A'
        first = self.upload('classes', 'import', body)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['counts']['CREATE'], 1)
        self.assertFalse(first.data['idempotent_replay'])

        job = MigrationJob.objects.get(
            school=self.school,
            domain='classes',
            file_fingerprint=first.data['file_fingerprint'],
        )
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.create_count, 1)
        event_count = PlatformEvent.objects.filter(
            action='school.migration_completed',
            details__migration_job_id=job.pk,
        ).count()

        retry = self.upload('classes', 'import', body)
        self.assertEqual(retry.status_code, 200, retry.data)
        self.assertTrue(retry.data['idempotent_replay'])
        self.assertEqual(retry.data['counts']['REUSE'], 1)
        self.assertEqual(MigrationJob.objects.filter(pk=job.pk).count(), 1)
        job.refresh_from_db()
        self.assertEqual(job.create_count, 1)
        self.assertEqual(job.reuse_count, 0)
        self.assertEqual(
            PlatformEvent.objects.filter(
                action='school.migration_completed',
                details__migration_job_id=job.pk,
            ).count(),
            event_count,
        )

    def test_batch20_historical_evidence_import_preserves_current_placement(self):
        current = AcademicSession.objects.create(
            school=self.school, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 18), is_current=True,
        )
        Term.objects.create(
            session=current, name='first',
            start_date=date(2026, 9, 1), end_date=date(2026, 12, 18), is_current=True,
        )
        self.assertEqual(
            self.upload('classes', 'import', 'class_level,class_arm\nJSS1,A\nJSS2,A').data['counts']['CREATE'],
            2,
        )
        self.assertEqual(
            self.upload('subjects', 'import', 'code,name,class_level\nMATH,Mathematics,JSS1').data['counts']['CREATE'],
            1,
        )
        student_import = self.upload(
            'students', 'import',
            'student_ref,first_name,last_name,class_level,class_arm,dob\nOLD-20,Ada,Legacy,JSS2,A,2013-01-02',
        )
        self.assertEqual(student_import.data['counts']['CREATE'], 1, student_import.data)
        student = StudentProfile.objects.get(school=self.school)
        current_arm_id = student.current_class_id

        old_session = self.upload(
            'historical_sessions', 'import',
            'session,start_date,end_date\n2025/26,2025-09-08,2026-07-17',
        )
        self.assertEqual(old_session.data['counts']['CREATE'], 1, old_session.data)
        old_term = self.upload(
            'historical_terms', 'import',
            'session,term,start_date,end_date\n2025/26,first,2025-09-08,2025-12-19',
        )
        self.assertEqual(old_term.data['counts']['CREATE'], 1, old_term.data)
        placement = self.upload(
            'historical_enrollments', 'import',
            'student_ref,session,class_level,class_arm,enrolled_on,exited_on,status,entry_reason\n'
            'OLD-20,2025/26,JSS1,A,2025-09-08,2026-07-17,completed,migration',
        )
        self.assertEqual(placement.data['counts']['CREATE'], 1, placement.data)

        result = self.upload(
            'historical_results', 'import',
            'student_ref,session,term,subject_code,class_level,class_arm,first_test,second_test,assignment,project,practical,exam_score,is_published\n'
            'OLD-20,2025/26,first,MATH,JSS1,A,8,7,7,4,4,50,true',
        )
        self.assertEqual(result.data['counts']['CREATE'], 1, result.data)
        attendance = self.upload(
            'historical_attendance', 'import',
            'student_ref,session,term,class_level,class_arm,date,status,remark\n'
            'OLD-20,2025/26,first,JSS1,A,2025-10-10,present,Imported register',
        )
        self.assertEqual(attendance.data['counts']['CREATE'], 1, attendance.data)

        student.refresh_from_db()
        self.assertEqual(student.current_class_id, current_arm_id)
        historical = AcademicSession.objects.get(school=self.school, name='2025/26')
        self.assertFalse(historical.is_current)
        old_enrollment = SessionEnrollment.objects.get(
            school=self.school, student=student, session=historical
        )
        self.assertEqual(old_enrollment.status, 'completed')
        self.assertEqual(old_enrollment.class_arm.class_level.name, 'JSS1')

        from gradebook.models import ScoreEntry
        score = ScoreEntry.objects.get(school=self.school, student=student.user, session=historical)
        self.assertEqual(score.total_score, Decimal('80.00'))
        self.assertTrue(score.is_published)
        self.assertEqual(score.class_arm.class_level.name, 'JSS1')

        from attendance.models import AttendanceRecord
        record = AttendanceRecord.objects.get(
            attendance_session__school=self.school,
            attendance_session__term__session=historical,
            student=student.user,
        )
        self.assertEqual(record.status, 'present')
        self.assertTrue(record.attendance_session.is_finalized)

    def test_batch20_conflicts_are_reviewed_not_overwritten(self):
        first = self.upload(
            'historical_sessions', 'import',
            'session,start_date,end_date\n2024/25,2024-09-09,2025-07-18',
        )
        self.assertEqual(first.data['counts']['CREATE'], 1, first.data)
        conflicting = self.upload(
            'historical_sessions', 'import',
            'session,start_date,end_date\n2024/25,2024-09-16,2025-07-25',
        )
        self.assertEqual(conflicting.data['counts']['REVIEW'], 1, conflicting.data)
        self.assertEqual(conflicting.data['counts']['REJECT'], 0)
        session = AcademicSession.objects.get(school=self.school, name='2024/25')
        self.assertEqual(session.start_date, date(2024, 9, 9))

        conflict = MigrationConflict.objects.get(job_id=conflicting.data['job_id'])
        self.assertEqual(conflict.status, 'open')
        listing = self.client.get('/api/migration/conflicts/?status=open')
        self.assertEqual(listing.status_code, 200, listing.data)
        self.assertEqual(listing.data[0]['conflict_type'], 'session_dates')

        resolved = self.client.patch(
            '/api/migration/conflicts/',
            {'id': conflict.pk, 'action': 'resolved', 'resolution': {'decision': 'keep_existing'}},
            format='json',
        )
        self.assertEqual(resolved.status_code, 200, resolved.data)
        conflict.refresh_from_db()
        self.assertEqual(conflict.status, 'resolved')
        self.assertEqual(conflict.resolved_by, self.admin)

    def test_batch20_mapping_profiles_and_job_history_are_tenant_scoped(self):
        saved = self.client.post('/api/migration/mappings/', {
            'domain': 'students',
            'name': 'Legacy SIS students',
            'source_system': 'Legacy SIS',
            'mappings': {'Registration Number': 'student_ref', 'Surname': 'last_name'},
        }, format='json')
        self.assertEqual(saved.status_code, 201, saved.data)
        self.assertEqual(MigrationMappingProfile.objects.filter(school=self.school).count(), 1)

        mappings = self.client.get('/api/migration/mappings/?domain=students')
        self.assertEqual(mappings.status_code, 200, mappings.data)
        self.assertEqual(len(mappings.data), 1)
        self.assertEqual(mappings.data[0]['source_system'], 'Legacy SIS')

        self.upload('classes', 'import', 'class_level,class_arm\nJSS1,A')
        jobs = self.client.get('/api/migration/jobs/')
        self.assertEqual(jobs.status_code, 200, jobs.data)
        self.assertTrue(any(row['domain'] == 'classes' for row in jobs.data))

        foreign_admin = CustomUser.objects.create_user(
            email='admin@migration-other.test', password='test',
            school=self.other, role='school_admin', must_change_password=False,
        )
        foreign_client = APIClient(HTTP_X_SCHOOL_SLUG=self.other.slug)
        foreign_client.force_authenticate(foreign_admin)
        self.assertEqual(foreign_client.get('/api/migration/jobs/').data, [])
        self.assertEqual(foreign_client.get('/api/migration/mappings/').data, [])
        self.assertEqual(foreign_client.get('/api/migration/conflicts/').data, [])
