from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
import sys

from django.contrib.auth import get_user_model
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from academics.models import AcademicSession, Term
from curriculum.models import CurriculumPlan, CurriculumWeek, CurriculumTopic
from enrollment.models import ClassArm, ClassLevel, StaffProfile, StudentProfile, Subject, SubjectAssignment
from gradebook.models import ScoreEntry, TermScoring
from tenants.models import School
from .models import Question, CBTExam, StudentExamSession, SubjectAssessmentMode, ExamPaper, OnlineAssignment
from .gradebook import integrate_component


class AssessmentDeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.school = School.objects.create(name='Assessment School', slug='assessment-school', subdomain='assessment-school', subscription_plan='premium')
        user = get_user_model()
        cls.admin = user.objects.create_user(email='admin@assessment.test', password='password', role='school_admin', school=cls.school, must_change_password=False)
        cls.teacher = user.objects.create_user(email='teacher@assessment.test', password='password', role='teacher', school=cls.school, must_change_password=False)
        staff = StaffProfile.objects.create(user=cls.teacher, school=cls.school)
        cls.student = user.objects.create_user(email='student@assessment.test', password='password', role='student', school=cls.school, must_change_password=False)
        cls.level = ClassLevel.objects.create(school=cls.school, name='SS2')
        cls.arm = ClassArm.objects.create(school=cls.school, class_level=cls.level, name='A')
        cls.subject = Subject.objects.create(school=cls.school, name='Chemistry', code='CHEM')
        cls.session = AcademicSession.objects.create(school=cls.school, name='2026/2027', start_date=date(2026,9,1), end_date=date(2027,7,31), is_current=True)
        cls.term = Term.objects.create(session=cls.session, name='first', start_date=date(2026,9,1), end_date=date(2026,12,18), is_current=True)
        StudentProfile.objects.create(user=cls.student, school=cls.school, current_class=cls.arm, guardian_email='parent@example.test')
        SubjectAssignment.objects.create(school=cls.school, teacher=staff, subject=cls.subject, class_arm=cls.arm, session=cls.session, term=cls.term)
        cls.policy = TermScoring.objects.create(school=cls.school, term=cls.term,
            components=[{'key':key,'name':key.title(),'maximum':maximum,'kind':kind} for key,maximum,kind in [
                ('assignment','10','assessment'),('test','10','assessment'),('cbt','30','assessment'),('theory','50','exam')]],
            bands=[{'grade':'F','remark':'Review','min_score':'0','max_score':'69.99'},
                   {'grade':'A','remark':'Excellent','min_score':'70','max_score':'100'}])
        plan = CurriculumPlan.objects.create(school=cls.school, term=cls.term, class_level=cls.level, subject=cls.subject)
        week = CurriculumWeek.objects.create(plan=plan, number=1)
        cls.topic = CurriculumTopic.objects.create(week=week, title='Atomic structure', position=1)

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def question(self, text='Atom', marks=1, question_type='mcq', source='bank', topic=None):
        return Question.objects.create(school=self.school, subject=self.subject, class_level=self.level,
            question_text=text, question_type=question_type, options=[{'id':'A','text':'Yes'},{'id':'B','text':'No'}] if question_type == 'mcq' else [],
            correct_answer='A' if question_type == 'mcq' else '', marks=marks, source=source,
            term=self.term if source == 'term' else None, curriculum_topic=topic)

    def exam(self, questions, component_key='cbt'):
        now = timezone.now()
        response = self.client.post('/api/cbt/exams/', {'title':'Chemistry CBT', 'subject':self.subject.pk,
            'class_arms':[self.arm.pk], 'term':self.term.pk, 'session':self.session.pk,
            'start_datetime':(now-timedelta(minutes=2)).isoformat(),
            'end_datetime':(now+timedelta(minutes=90)).isoformat(), 'duration_minutes':60,
            'selection_mode':'manual','manual_questions':[q.pk for q in questions],
            'component_key':component_key,'status':'published','randomize_options':False}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return CBTExam.objects.get(pk=response.data['id'])

    def test_weighted_cbt_normalization_and_retry(self):
        first, second = self.question('Weighted correct', 42), self.question('Weighted wrong', 8)
        exam = self.exam([first, second])
        self.client.force_authenticate(self.student)
        started = self.client.post(f'/api/cbt/exams/{exam.pk}/start/')
        self.assertEqual(started.status_code, 200, started.data)
        self.assertNotIn('correct_answer', str(started.data))
        saved = self.client.post(f'/api/cbt/exams/{exam.pk}/save-answer/', {'question_id':first.pk,'selected_option':'A'}, format='json')
        self.assertEqual(saved.status_code, 200, saved.data)
        submitted = self.client.post(f'/api/cbt/exams/{exam.pk}/submit/')
        self.assertEqual(submitted.status_code, 200, submitted.data)
        self.assertEqual(self.client.post(f'/api/cbt/exams/{exam.pk}/submit/').status_code, 200)
        attempt = StudentExamSession.objects.get(exam=exam, student=self.student)
        self.assertEqual((attempt.raw_score, attempt.raw_maximum), (Decimal('42'), Decimal('50')))
        self.client.force_authenticate(self.admin)
        pushed = self.client.post(f'/api/cbt/exams/{exam.pk}/push-to-gradebook/')
        self.assertEqual(pushed.status_code, 200, pushed.data)
        self.assertEqual(pushed.data['updated'], 1)
        self.assertEqual(self.client.post(f'/api/cbt/exams/{exam.pk}/push-to-gradebook/').data['updated'], 0)
        entry = ScoreEntry.objects.get(student=self.student, subject=self.subject, term=self.term)
        self.assertEqual(entry.component_scores['cbt'], '25.20')
        self.assertEqual(entry.component_sources['cbt'], f'cbt:{exam.pk}')
        manual = self.client.patch(f'/api/gradebook/entries/{entry.pk}/', {'student':self.student.pk,
            'subject':self.subject.pk, 'class_arm':self.arm.pk, 'term':self.term.pk, 'session':self.session.pk,
            'component_scores':{'assignment':'8','test':'7','cbt':'25.20','theory':'44'}}, format='json')
        self.assertEqual(manual.status_code, 200, manual.data)
        entry.refresh_from_db()
        self.assertEqual(entry.total_score, Decimal('84.20'))
        self.assertEqual(entry.review_state, 'draft')
        tamper = self.client.patch(f'/api/gradebook/entries/{entry.pk}/', {'student':self.student.pk,
            'subject':self.subject.pk, 'class_arm':self.arm.pk, 'term':self.term.pk, 'session':self.session.pk,
            'component_scores':{'assignment':'8','test':'7','cbt':'30','theory':'44'}}, format='json')
        self.assertEqual(tamper.status_code, 400, tamper.data)

    def test_basic_term_questions_are_not_reusable(self):
        self.school.subscription_plan = 'basic'; self.school.save(update_fields=['subscription_plan'])
        payload = {'subject':self.subject.pk,'class_level':self.level.pk,'question_text':'Term question',
                   'question_type':'mcq','options':[{'id':'A','text':'Yes'},{'id':'B','text':'No'}], 'correct_answer':'A'}
        created = self.client.post('/api/cbt/questions/', payload, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        question = Question.objects.get(pk=created.data['id'])
        self.assertEqual((question.source, question.term_id), ('term', self.term.pk))
        self.assertEqual(self.client.get('/api/cbt/topics/').status_code, 403)
        exam = self.exam([question])
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(f'/api/cbt/exams/{exam.pk}/start/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/cbt/exams/{exam.pk}/save-answer/',
            {'question_id':question.pk,'selected_option':'A'},format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/cbt/exams/{exam.pk}/submit/').status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(f'/api/cbt/exams/{exam.pk}/push-to-gradebook/').status_code, 200)
        next_term = Term.objects.create(session=self.session, name='second', start_date=date(2027,1,1),
                                        end_date=date(2027,4,15), is_current=True)
        self.assertEqual(self.client.get('/api/cbt/questions/').data['results'] if isinstance(self.client.get('/api/cbt/questions/').data, dict) else self.client.get('/api/cbt/questions/').data, [])
        self.assertEqual(self.client.post('/api/cbt/questions/', {**payload, 'term':self.term.pk}, format='json').status_code, 400)
        self.assertTrue(StudentExamSession.objects.get(exam=exam).question_snapshot)
        self.assertEqual(ScoreEntry.objects.get(student=self.student).component_scores['cbt'], '30.00')

    def test_paper_generation_review_approval_and_pdf(self):
        SubjectAssessmentMode.objects.create(school=self.school, term=self.term, class_level=self.level, subject=self.subject, mode='paper')
        first = self.question('First objective', topic=self.topic)
        second = self.question('Replacement objective', topic=self.topic)
        self.question('Explain atoms', question_type='theory', topic=self.topic)
        created = self.client.post('/api/cbt/papers/', {'term':self.term.pk,'class_level':self.level.pk,
            'subject':self.subject.pk,'title':'Term paper','duration_minutes':60,
            'blueprint':[{'topic_id':self.topic.pk,'objective':1,'theory':1}]}, format='json')
        self.assertEqual(created.status_code, 201, created.data)
        url = f'/api/cbt/papers/{created.data["id"]}/'
        generated = self.client.post(url+'generate/')
        self.assertEqual(generated.status_code, 200, generated.data)
        self.assertEqual(len(generated.data['question_snapshot']), 2)
        self.assertEqual(self.client.post(url+'generate/').data['question_snapshot'], generated.data['question_snapshot'])
        index = next(i for i,row in enumerate(generated.data['question_snapshot']) if row['section']=='objective')
        replacement = second if generated.data['question_snapshot'][index]['id']==first.pk else first
        self.assertEqual(self.client.post(url+'replace/', {'index':index,'question_id':replacement.pk}, format='json').status_code, 200)
        self.assertEqual(self.client.post(url+'submit/').status_code, 200)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.post(url+'approve/').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(url+'approve/').status_code, 200)
        self.assertEqual(self.client.post(url+'replace/', {'index':index,'question_id':first.pk}, format='json').status_code, 400)
        rendered = []
        fake_pdf = SimpleNamespace(HTML=lambda string: (rendered.append(string) or SimpleNamespace(write_pdf=lambda: b'%PDF-1.7 test')))
        with patch.dict(sys.modules, {'weasyprint': fake_pdf}):
            pdf = self.client.get(url+'pdf/')
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertNotIn('DRAFT - NOT APPROVED', rendered[0])

    def test_practice_and_graded_assignment(self):
        self.client.force_authenticate(self.teacher)
        due = (timezone.now()+timedelta(days=2)).isoformat()
        base = {'term':self.term.pk,'class_arm':self.arm.pk,'subject':self.subject.pk,
                'title':'Homework','instructions':'Explain the topic','due_at':due,'maximum':'10'}
        practice = self.client.post('/api/cbt/assignments/', {**base,'kind':'practice'}, format='json')
        self.assertEqual(practice.status_code, 201, practice.data)
        graded = self.client.post('/api/cbt/assignments/', {**base,'kind':'graded','component_key':'assignment'}, format='json')
        self.assertEqual(graded.status_code, 201, graded.data)
        self.assertEqual(self.client.post('/api/cbt/assignments/', {**base,'kind':'graded','component_key':'assignment'}, format='json').status_code, 400)
        for assignment in (practice, graded):
            url = f'/api/cbt/assignments/{assignment.data["id"]}/'
            self.assertEqual(self.client.post(url+'publish/').status_code, 200)
            self.client.force_authenticate(self.student)
            self.assertEqual(self.client.post(url+'save-response/', {'text':'My answer'}, format='json').status_code, 200)
            self.assertEqual(self.client.post(url+'submit/').status_code, 200)
            self.assertEqual(self.client.post(url+'submit/').status_code, 200)
            self.assertEqual(self.client.post(url+'save-response/', {'text':'change'}, format='json').status_code, 400)
            self.client.force_authenticate(self.teacher)
            submission_id = self.client.get(url+'submissions/').data[0]['id']
            marked = self.client.post(url+'mark/', {'submission_id':submission_id,'score':'8','feedback':'Good'}, format='json')
            self.assertEqual(marked.status_code, 200, marked.data)
            self.assertEqual(self.client.post(url+'mark/', {'submission_id':submission_id,'score':'8','feedback':'Good'}, format='json').status_code, 200)
            if assignment == practice:
                self.assertFalse(ScoreEntry.objects.exists())
        entry = ScoreEntry.objects.get()
        self.assertEqual(entry.component_scores['assignment'], '8.00')
        self.assertEqual(entry.component_sources['assignment'], f'assignment:{graded.data["id"]}')

    def test_basic_plan_blocks_premium_assessment_endpoints(self):
        self.school.subscription_plan = 'basic'; self.school.save(update_fields=['subscription_plan'])
        for endpoint in ('/api/cbt/modes/', '/api/cbt/papers/', '/api/cbt/assignments/',
                         '/api/cbt/questions/curriculum-topics/'):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(self.client.get(endpoint).status_code, 403)
        self.assertEqual(self.client.get('/api/cbt/questions/').status_code, 200)

    def test_question_answer_validation_and_long_fill_blank_answer(self):
        base = {'subject':self.subject.pk,'class_level':self.level.pk,'question_text':'Name the particle',
                'question_type':'mcq','options':[{'id':'A','text':'Proton'},{'id':'B','text':'Neutron'}]}
        self.assertEqual(self.client.post('/api/cbt/questions/', {**base,'correct_answer':'C'}, format='json').status_code, 400)
        expected = 'electromagnetic radiation'
        created = self.client.post('/api/cbt/questions/', {**base,'question_type':'fill_blank',
            'options':[],'correct_answer':expected},format='json')
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(Question.objects.get(pk=created.data['id']).correct_answer, expected)

    def test_paper_list_queries_remain_bounded_as_papers_grow(self):
        def make_paper(index):
            return ExamPaper.objects.create(school=self.school, term=self.term, subject=self.subject,
                class_level=self.level, title=f'Paper {index}', duration_minutes=60,
                blueprint=[{'topic_id':self.topic.pk,'objective':1,'theory':0}], created_by=self.admin)
        make_paper(0)
        with CaptureQueriesContext(connection) as first:
            self.assertEqual(self.client.get('/api/cbt/papers/').status_code, 200)
        for index in range(1, 20):
            make_paper(index)
        with CaptureQueriesContext(connection) as twenty:
            self.assertEqual(self.client.get('/api/cbt/papers/').status_code, 200)
        self.assertLessEqual(len(twenty), len(first) + 2)

    def test_student_cannot_read_answer_keys_or_other_class_assignments(self):
        question = self.question(topic=self.topic)
        other_arm = ClassArm.objects.create(school=self.school, class_level=self.level, name='B')
        due = (timezone.now()+timedelta(days=2)).isoformat()
        payload = {'term':self.term.pk,'subject':self.subject.pk,'title':'Objective practice',
                   'instructions':'Choose one','due_at':due,'maximum':'10','kind':'practice',
                   'question_ids':[question.pk]}
        own = self.client.post('/api/cbt/assignments/', {**payload,'class_arm':self.arm.pk}, format='json')
        other = self.client.post('/api/cbt/assignments/', {**payload,'class_arm':other_arm.pk}, format='json')
        self.assertEqual(own.status_code, 201, own.data)
        self.assertEqual(other.status_code, 201, other.data)
        for assignment in (own, other):
            self.assertEqual(self.client.post(f'/api/cbt/assignments/{assignment.data["id"]}/publish/').status_code, 200)
        self.client.force_authenticate(self.student)
        listed = self.client.get('/api/cbt/assignments/')
        self.assertEqual(listed.status_code, 200, listed.data)
        records = listed.data['results'] if isinstance(listed.data, dict) else listed.data
        self.assertEqual([row['id'] for row in records], [own.data['id']])
        self.assertNotIn('correct_answer', str(records))
        self.assertEqual(self.client.get(f'/api/cbt/assignments/{other.data["id"]}/').status_code, 404)
        self.assertEqual(self.client.get('/api/cbt/questions/').status_code, 403)
        self.assertEqual(self.client.get('/api/cbt/papers/').status_code, 403)
        self.assertEqual(self.client.post(f'/api/cbt/assignments/{own.data["id"]}/save-response/',
            {'answers':{str(question.pk):'A'}},format='json').status_code, 200)
        self.assertEqual(self.client.post(f'/api/cbt/assignments/{own.data["id"]}/submit/').status_code, 200)
        hidden = self.client.get(f'/api/cbt/assignments/{own.data["id"]}/my-submission/').data
        self.assertIsNone(hidden['score'])

    def test_paper_shortage_is_actionable_and_draft_is_marked(self):
        SubjectAssessmentMode.objects.create(school=self.school, term=self.term, class_level=self.level,
                                             subject=self.subject, mode='paper')
        question = self.question('One atom question', topic=self.topic)
        response = self.client.post('/api/cbt/papers/', {'term':self.term.pk,'class_level':self.level.pk,
            'subject':self.subject.pk,'title':'Short paper','duration_minutes':60,
            'blueprint':[{'topic_id':self.topic.pk,'objective':2,'theory':0}]}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f'/api/cbt/papers/{response.data["id"]}/'
        shortage = self.client.post(url+'generate/')
        self.assertEqual(shortage.status_code, 400)
        self.assertIn('only 1 eligible', str(shortage.data))
        self.question('Second atom question', topic=self.topic)
        self.assertEqual(self.client.post(url+'generate/').status_code, 200)
        rendered = []
        fake_pdf = SimpleNamespace(HTML=lambda string: (rendered.append(string) or SimpleNamespace(write_pdf=lambda: b'%PDF test')))
        with patch.dict(sys.modules, {'weasyprint': fake_pdf}):
            self.assertEqual(self.client.get(url+'pdf/').status_code, 200)
        self.assertIn('DRAFT - NOT APPROVED', rendered[0])
        self.assertIn(question.question_text, rendered[0])

    def test_archived_questions_and_attempted_exam_are_retained(self):
        question = self.question()
        exam = self.exam([question])
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.post(f'/api/cbt/exams/{exam.pk}/start/').status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f'/api/cbt/questions/{question.pk}/').status_code, 204)
        question.refresh_from_db()
        self.assertFalse(question.is_active)
        self.assertEqual(self.client.delete(f'/api/cbt/exams/{exam.pk}/').status_code, 400)
        self.assertTrue(StudentExamSession.objects.filter(exam=exam, student=self.student).exists())

    def test_second_school_cannot_use_first_school_assessment_records(self):
        other = School.objects.create(name='Other Assessment School', slug='other-assessment',
                                      subdomain='other-assessment', subscription_plan='premium')
        other_admin = get_user_model().objects.create_user(email='admin@other-assessment.test',
            password='password', role='school_admin', school=other, must_change_password=False)
        question = self.question(topic=self.topic)
        self.client.force_authenticate(other_admin)
        self.client.defaults['HTTP_X_SCHOOL_SLUG'] = other.slug
        self.assertEqual(self.client.get(f'/api/cbt/questions/{question.pk}/').status_code, 404)
        created = self.client.post('/api/cbt/questions/', {'subject':self.subject.pk,
            'class_level':self.level.pk,'question_text':'Cross school','question_type':'mcq',
            'options':[{'id':'A','text':'Yes'}],'correct_answer':'A'},format='json')
        self.assertEqual(created.status_code, 400)
        self.assertFalse(Question.objects.filter(school=other).exists())


@skipUnless(connection.vendor == 'postgresql', 'Concurrent assessment integration requires isolated PostgreSQL.')
class AssessmentConcurrencyTests(TransactionTestCase):
    def test_two_retries_create_one_gradebook_component(self):
        school = School.objects.create(name='Concurrent Assessment', slug='concurrent-assessment',
                                       subdomain='concurrent-assessment', subscription_plan='premium')
        user = get_user_model()
        student = user.objects.create_user(email='concurrent-student@assessment.test', password='password',
                                           role='student', school=school, must_change_password=False)
        level = ClassLevel.objects.create(school=school, name='SS1')
        arm = ClassArm.objects.create(school=school, class_level=level, name='A')
        subject = Subject.objects.create(school=school, name='Physics', code='PHY')
        session = AcademicSession.objects.create(school=school, name='2026/2027',
            start_date=date(2026,9,1), end_date=date(2027,7,31))
        term = Term.objects.create(session=session, name='first',
            start_date=date(2026,9,1), end_date=date(2026,12,18))
        TermScoring.objects.create(school=school, term=term,
            components=[{'key':'cbt','name':'CBT','maximum':'100','kind':'exam'}],
            bands=[{'grade':'F','remark':'Review','min_score':'0','max_score':'69.99'},
                   {'grade':'A','remark':'Excellent','min_score':'70','max_score':'100'}])
        barrier = Barrier(2)

        def push():
            try:
                barrier.wait(timeout=10)
                return integrate_component(school=school, student=student, subject=subject, term=term,
                    class_arm=arm, key='cbt', source='cbt:1', raw_score='42', raw_maximum='50')[1]
            finally:
                connections['default'].close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [future.result(timeout=20) for future in [pool.submit(push), pool.submit(push)]]
        self.assertCountEqual(results, [True, False])
        self.assertEqual(ScoreEntry.objects.filter(student=student, subject=subject, term=term).count(), 1)
        entry = ScoreEntry.objects.get(student=student, subject=subject, term=term)
        self.assertEqual(entry.component_scores['cbt'], '84.00')
