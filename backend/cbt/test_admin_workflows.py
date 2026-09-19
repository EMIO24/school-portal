from datetime import date
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from tenants.models import School
from academics.models import AcademicSession, Term
from enrollment.models import ClassLevel, ClassArm, Subject, StudentProfile
from notifications.models import NotificationLog
from cbt.models import Question
from cbt.docx_import import question_template
import io
import zipfile

class AdminWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name='Workflow School', slug='workflow-school', subdomain='workflow-school', subscription_plan='premium')
        cls.admin = get_user_model().objects.create_user(email='admin@workflow.test', password='testpass', role='school_admin', must_change_password=False, school=cls.school)
        cls.level = ClassLevel.objects.create(school=cls.school, name='JSS1')
        cls.arm = ClassArm.objects.create(school=cls.school, class_level=cls.level, name='A')
        cls.subject = Subject.objects.create(school=cls.school, name='Math', code='MATH')
        cls.session = AcademicSession.objects.create(school=cls.school, name='2026/2027', start_date=date(2026,9,1), end_date=date(2027,7,31))
        cls.term = Term.objects.create(session=cls.session, name='first', start_date=date(2026,9,1), end_date=date(2026,12,18))
        cls.student = get_user_model().objects.create_user(email='student@workflow.test', password='testpass', role='student', school=cls.school)
        cls.profile = StudentProfile.objects.create(user=cls.student, school=cls.school, current_class=cls.arm, guardian_email='guardian@example.test')
    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)
    def exam(self):
        return dict(title='Rule test', subject=self.subject.id, class_arms=[self.arm.id], term=self.term.id, session=self.session.id,
                    start_datetime='2026-12-01T09:00:00Z', end_datetime='2026-12-01T10:00:00Z', duration_minutes=60,
                    selection_mode='random_from_bank', random_config=[dict(topic_id=None,difficulty='easy',count=5)], status='draft')
    def test_exam_rule_survives_create_configure_and_edit(self):
        response=self.client.post('/api/cbt/exams/', self.exam(), format='json')
        self.assertEqual(response.status_code,201,response.data)
        config=self.client.get(f'/api/cbt/exams/{response.data["id"]}/configuration/')
        self.assertEqual(config.status_code,200)
        self.assertEqual(config.data['random_config'][0]['count'],5)
        self.assertEqual(config.data['class_arms'],[self.arm.id])
        edited=self.client.patch(f'/api/cbt/exams/{response.data["id"]}/', {'random_config':[dict(topic_id=None,difficulty=None,count=40)]}, format='json')
        self.assertEqual(edited.status_code,200,edited.data)
        config=self.client.get(f'/api/cbt/exams/{response.data["id"]}/configuration/')
        self.assertEqual(config.data['random_config'][0]['count'],40)
    def test_invalid_rule_is_explained(self):
        payload=self.exam(); payload['random_config']=[{'count':0}]
        response=self.client.post('/api/cbt/exams/',payload,format='json')
        self.assertEqual(response.status_code,400)
        self.assertIn('random_config',response.data)
    @override_settings(NOTIFICATIONS_CAPTURE_ONLY=True)
    def test_notification_capture_and_missing_recipient_validation(self):
        response=self.client.post('/api/notifications/send/',dict(channel='email',recipient_type='individual',student_ids=[self.profile.id],subject='Test',message='Hello {student_name}'),format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['captured'],1)
        self.assertEqual(response.data['sent'],0)
        self.assertTrue(NotificationLog.objects.get().error_message.startswith('Captured locally'))
        response=self.client.post('/api/notifications/send/',dict(channel='email',recipient_type='individual',student_ids=[],subject='Test',message='Hello'),format='json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(NotificationLog.objects.count(),1)
    @override_settings(NOTIFICATIONS_CAPTURE_ONLY=True)
    def test_missing_contact_is_reported(self):
        response=self.client.post('/api/notifications/send/',dict(channel='sms',recipient_type='all_parents',message='Hello'),format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.data['skipped'],1)
        self.assertEqual(response.data['captured'],0)
    def test_40_docx_questions_become_40_distinct_records(self):
        with zipfile.ZipFile(io.BytesIO(question_template())) as original:
            parts={name:original.read(name) for name in original.namelist()}
        paragraphs=''.join(f'<w:p><w:r><w:t>{line}</w:t></w:r></w:p>' for i in range(40) for line in [f'Question: Item {i+1}', 'A. Yes','B. No','Answer: A'])
        parts['word/document.xml']=('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+paragraphs+'</w:body></w:document>').encode()
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as archive:
            for name,data in parts.items(): archive.writestr(name,data)
        response=self.client.post('/api/cbt/questions/docx-preview/',{'file':SimpleUploadedFile('forty.docx',out.getvalue())},format='multipart')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(len(response.data['questions']),40)
        payload=[{**question,'subject':self.subject.id,'class_level':self.level.id} for question in response.data['questions']]
        imported=self.client.post('/api/cbt/questions/bulk-import/',payload,format='json')
        self.assertEqual(imported.status_code,201,imported.data)
        self.assertEqual(imported.data['imported'],40)
        self.assertEqual(Question.objects.count(),40)
        self.assertEqual(Question.objects.values('question_text').distinct().count(),40)