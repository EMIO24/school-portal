from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.template.loader import render_to_string
from accounts.models import ParentStudentLink
from academics.models import Term
from enrollment import test_operations as operations
from enrollment.models import Subject, StudentProfile
from .models import ScoreEntry, TermScoring, GradeScale
from .scoring import ScoringInput


def configuration(maxima=(10,10,10,70)):
    return {'components':[{'key':f'c{i}','name':f'Assessment {i+1}','maximum':str(n),'kind':'exam' if i==len(maxima)-1 else 'assessment'} for i,n in enumerate(maxima)],
        'bands':[{'grade':'F','remark':'Review','min_score':'0','max_score':'69.99'},
                 {'grade':'A','remark':'Excellent','min_score':'70','max_score':'100'}]}


class AcademicWorkflowTests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)

    def setUp(self):
        operations.BasicOperationsTests.setUp(self)
        self.score.delete()
        self.scope={'class_arm':self.arm.pk,'subject':self.subject.pk,'term':self.term.pk,'session':self.session.pk}
        self.config_url=f'/api/gradebook/configuration/?term={self.term.pk}'
        self.result_url=f'/api/results/slip-data/{self.student.pk}/?term={self.term.pk}'

    def configure(self, data=None):
        response=self.client.put(self.config_url,data or configuration(),format='json')
        self.assertEqual(response.status_code,200,response.data)

    def save_scores(self, scores=None):
        return self.client.post('/api/gradebook/entries/bulk-update/',{**self.scope,'scores':[{'student_id':self.student.pk,'component_scores':scores or {'c0':8,'c1':9,'c2':7,'c3':48}}]},format='json')

    def action(self,name,status=200):
        response=self.client.post(f'/api/gradebook/entries/{name}/',self.scope,format='json')
        self.assertEqual(response.status_code,status,response.data)
        if status == 200:
            self.assertEqual(response.data[{'submit':'submitted','approve':'approved','publish':'published'}[name]],1)
        return response

    def publish(self):
        self.client.force_authenticate(self.teacher);self.action('submit')
        self.action('approve',403);self.action('publish',403)
        self.client.force_authenticate(self.admin);self.action('approve');self.action('publish')

    def test_three_school_structures_complete_lifecycle(self):
        for maxima in [(10,10,10,70),(20,20,60),(40,60)]:
            with self.subTest(maxima=maxima):
                self.configure(configuration(maxima))
                self.client.force_authenticate(self.teacher)
                response=self.save_scores({f'c{i}':n for i,n in enumerate(maxima)})
                self.assertEqual(response.status_code,200,response.data)
                entry=ScoreEntry.objects.get();self.assertEqual(entry.total_score,100);self.assertEqual(entry.grade,'A')
                self.publish()
                self.client.force_authenticate(self.student)
                result=self.client.get(self.result_url);self.assertEqual(result.status_code,200)
                self.assertEqual([Decimal(c['maximum']) for c in result.data['score_rows'][0]['components']],list(map(Decimal,maxima)))
                self.client.force_authenticate(self.admin)
                ScoreEntry.objects.all().delete();TermScoring.objects.all().delete()

    def test_assessment_validation(self):
        invalid=[(9,10,10,70),(11,10,10,70),(0,30,70),(-1,31,70)]
        for maxima in invalid:
            with self.subTest(maxima=maxima):
                self.assertEqual(self.client.put(self.config_url,configuration(maxima),format='json').status_code,400)
        for field,value in [('key','c0'),('name','Assessment 1'),('name',''),('key','invalid key'),('key','is_published')]:
            data=configuration();data['components'][1][field]=value
            self.assertFalse(ScoringInput(data=data).is_valid())
        self.assertFalse(TermScoring.objects.exists())

    def test_grading_validation(self):
        for field,value in [('min_score','60'),('min_score','71'),('max_score','69'),('max_score','101'),('grade','F')]:
            data=configuration();data['bands'][1][field]=value
            with self.subTest(field=field,value=value):
                self.assertEqual(self.client.put(self.config_url,data,format='json').status_code,400)

    def test_component_limits_and_missing_are_not_zero(self):
        self.configure()
        for values in [{'c0':11},{'c3':71},{'c0':-1},{'unknown':1}]:
            self.assertEqual(self.save_scores(values).status_code,400)
        self.assertEqual(self.save_scores({'c0':0}).status_code,200)
        self.action('submit',400)
        self.assertEqual(ScoreEntry.objects.get().grade,'')
        self.assertEqual(self.save_scores(dict.fromkeys(['c0','c1','c2','c3'],0)).status_code,200)
        self.action('submit')

    def test_history_remains_authoritative_after_future_changes(self):
        self.configure();self.assertEqual(self.save_scores().status_code,200);self.publish()
        entry=ScoreEntry.objects.get();self.assertEqual(entry.total_score,72);self.assertEqual(entry.grade,'A')
        before=self.client.get(self.result_url).data['score_rows']
        self.assertEqual(self.client.put(self.config_url,configuration((40,60)),format='json').status_code,400)
        with self.assertRaises(ProtectedError):entry.policy.delete()
        entry.component_scores['c3']='0'
        with self.assertRaises(ValidationError):entry.save()
        future=Term.objects.create(session=self.session,name='second',start_date=date(2027,1,1),end_date=date(2027,4,1))
        data=configuration((40,60));data['bands'][0]['max_score']='74.99';data['bands'][1]['min_score']='75'
        self.assertEqual(self.client.put(f'/api/gradebook/configuration/?term={future.pk}',data,format='json').status_code,200)
        GradeScale.objects.filter(school=self.school).update(remark='Changed')
        after=self.client.get(self.result_url).data
        self.assertEqual(before,after['score_rows'])
        html=render_to_string('result_slip.html',after)
        self.assertIn('Assessment 4: 48.00 / 70.00',html)
        self.assertIn('Excellent',html)

    def test_unpublished_and_ownership_protection(self):
        self.configure();self.save_scores()
        parent=self.user('parent','parent');stranger=self.user('stranger','parent');peer=self.user('peer','student')
        StudentProfile.objects.create(school=self.school,user=peer)
        ParentStudentLink.objects.create(school=self.school,parent=parent,student=self.profile)
        for actor in [self.student,parent,peer,stranger]:
            self.client.force_authenticate(actor)
            self.assertEqual(self.client.get(self.result_url).status_code,403)
        self.publish()
        for actor,expected in [(self.student,200),(parent,200),(peer,403),(stranger,403)]:
            self.client.force_authenticate(actor);self.assertEqual(self.client.get(self.result_url).status_code,expected)

    def test_assignment_and_tenant_attacks(self):
        self.configure();self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.put(self.config_url,configuration(),format='json').status_code,403)
        subject=Subject.objects.create(school=self.school,name='Other',code='OTHER')
        self.scope['subject']=subject.pk;self.assertEqual(self.save_scores().status_code,403)
        self.scope['subject']=self.subject.pk
        self.assignment.delete();self.assertEqual(self.save_scores().status_code,403)
        self.client.force_authenticate(self.admin)
        self.session.school=self.other;self.session.save()
        self.assertEqual(self.client.get(self.config_url).status_code,404)
        self.action('submit',404)

    def test_submission_locks_and_audited_reopen(self):
        self.configure();self.save_scores();self.action('publish',400);self.action('submit')
        self.assertEqual(self.save_scores().status_code,400)
        entry=ScoreEntry.objects.get()
        self.assertEqual(self.client.delete(f'/api/gradebook/entries/{entry.pk}/').status_code,400)
        response=self.client.post('/api/gradebook/entries/reopen/',{'entry_ids':[entry.pk],'reason':'Correct the assessment entry'},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.save_scores().status_code,200)
        from tenants.models import PlatformEvent
        self.assertTrue(PlatformEvent.objects.filter(action='school.results_reopened',actor=self.admin).exists())

    def test_transition_rolls_back_if_audit_write_fails(self):
        self.configure();self.save_scores()
        with patch('gradebook.lifecycle.PlatformEvent.objects.create',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):self.action('submit')
        self.assertEqual(ScoreEntry.objects.get().review_state,'draft')

    def test_partial_update_preserves_other_component_values(self):
        self.configure();self.save_scores();entry=ScoreEntry.objects.get()
        self.assertEqual(self.client.patch(f'/api/gradebook/entries/{entry.pk}/',{},format='json').status_code,200)
        entry.refresh_from_db();self.assertEqual(entry.total_score,72)

    def test_readiness_requires_valid_term_configuration(self):
        self.client.post(f'/api/sessions/{self.session.pk}/set-current/')
        self.client.post(f'/api/terms/{self.term.pk}/set-current/')
        def ready():return {s['key']:s['complete'] for s in self.client.get('/api/school/setup/').data['steps']}
        self.assertFalse(ready()['assessment']);self.assertFalse(ready()['grading'])
        self.configure();self.assertTrue(ready()['assessment']);self.assertTrue(ready()['grading'])
        self.assertEqual(self.client.get('/api/school/setup/').data['assessment']['c3'],'70.00')

    def test_bulk_validation_and_roster_completeness_are_atomic(self):
        self.configure()
        peer=self.user('classmate','student')
        StudentProfile.objects.create(school=self.school,user=peer,current_class=self.arm)
        self.save_scores();self.action('submit',400)
        response=self.client.post('/api/gradebook/entries/bulk-update/',{**self.scope,'scores':[
            {'student_id':self.student.pk,'component_scores':{'c0':1,'c1':1,'c2':1,'c3':1}},
            {'student_id':peer.pk,'component_scores':{'c0':11}}]},format='json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(ScoreEntry.objects.get().total_score,72)

    def test_foreign_student_and_context_changes_rejected(self):
        self.configure();self.save_scores();entry=ScoreEntry.objects.get()
        foreign=self.user('foreign','student');foreign.school=self.other;foreign.save()
        response=self.client.patch(f'/api/gradebook/entries/{entry.pk}/',{'student':foreign.pk},format='json')
        self.assertEqual(response.status_code,400)
        future=Term.objects.create(session=self.session,name='second',start_date=date(2027,1,1),end_date=date(2027,4,1))
        response=self.client.patch(f'/api/gradebook/entries/{entry.pk}/',{'term':future.pk},format='json')
        self.assertEqual(response.status_code,400)
        entry.refresh_from_db();self.assertEqual(entry.term,self.term)

    def test_teacher_cannot_read_unassigned_subject_scores(self):
        self.configure();self.save_scores();entry=ScoreEntry.objects.get()
        self.assignment.delete();self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get(f'/api/gradebook/entries/{entry.pk}/').status_code,404)

    def test_published_remarks_and_domains_require_reopening(self):
        self.configure();self.save_scores();self.publish()
        self.assertEqual(self.client.patch(f'/api/results/remarks/{self.student.pk}/?term={self.term.pk}',{'principal_remark':'Changed'},format='json').status_code,400)
        for domain in ['affective','psychomotor']:
            response=self.client.put(f'/api/gradebook/{domain}/student/{self.student.pk}/term/{self.term.pk}/',{'class_arm':self.arm.pk},format='json')
            self.assertEqual(response.status_code,400,response.data)

    def test_legacy_published_records_remain_unmodified(self):
        entry=ScoreEntry.objects.create(school=self.school,student=self.student,class_arm=self.arm,subject=self.subject,session=self.session,term=self.term,exam_score=50,is_published=True)
        original=(entry.grade,entry.total_score)
        GradeScale.objects.filter(school=self.school).update(remark='Changed')
        data=self.client.get(self.result_url).data['score_rows'][0]
        entry.refresh_from_db()
        self.assertEqual((entry.grade,entry.total_score),original)
        self.assertEqual(data['grade'],original[0]);self.assertIsNone(entry.policy_id)
        self.assertEqual(data['grading_bands'],[])

    def test_decimal_grade_boundaries(self):
        self.configure()
        for exam,expected in [('39.99','F'),('40.00','A'),('70.00','A')]:
            response=self.save_scores({'c0':10,'c1':10,'c2':10,'c3':exam})
            self.assertEqual(response.status_code,200,response.data)
            self.assertEqual(ScoreEntry.objects.get().grade,expected)
