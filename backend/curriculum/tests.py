from datetime import date, time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import CustomUser
from academics.models import Holiday, Term
from enrollment import test_operations as operations
from enrollment.models import ClassArm, ClassLevel, StaffProfile, Subject, SubjectAssignment
from tenants.models import PlatformEvent
from timetable.models import LessonRecord, Period, TimetableEntry
from .models import CurriculumPlan, CurriculumTopic, LearningObjective, TopicCoverage


class CurriculumTests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)
    day = date(2026, 9, 21)

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)
        period = Period.objects.create(school=self.school, name='P1', start_time=time(8), end_time=time(9), order_index=1)
        self.slot = TimetableEntry.objects.create(school=self.school, term=self.term, class_arm=self.arm,
            subject=self.subject, teacher=self.teacher, day_of_week='MON', period=period)
        self.lesson_url = f'/api/timetable/lessons/{self.slot.pk}/{self.day}/'
        self.query = {'term': self.term.pk, 'class_level': self.level.pk, 'subject': self.subject.pk, 'class_arm': self.arm.pk}
        self.topic_payload = {'term': self.term.pk, 'class_level': self.level.pk, 'subject': self.subject.pk,
                              'week': 2, 'position': 1, 'title': 'Fractions', 'objectives': ['Identify fractions', 'Compare fractions']}

    def topic(self, **changes):
        response = self.client.post('/api/curriculum/plans/', {**self.topic_payload, **changes}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['topic']

    def lesson(self, outcome='delivered'):
        data = {'outcome': outcome, 'revision': 0}
        if outcome == 'substituted':
            substitute = CustomUser.objects.create_user(email='sub-curriculum@test.invalid', password='Example-12345!',
                school=self.school, role='teacher', must_change_password=False)
            StaffProfile.objects.create(school=self.school, user=substitute)
            data['actual_teacher'] = substitute.pk
            self.substitute = substitute
        response = self.client.put(self.lesson_url, data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data['id']

    def coverage(self, lesson, topic, state='partial', revision=0):
        return self.client.put(f'/api/curriculum/lessons/{lesson}/topics/{topic}/',
                               {'state': state, 'revision': revision}, format='json')

    def test_plan_hierarchy_order_objectives_and_term_history(self):
        second = self.topic(position=2, title='Decimals', week=3, objectives=['Place value'])
        first = self.topic()
        response = self.client.get('/api/curriculum/plans/', self.query)
        self.assertEqual(response.status_code, 200)
        weeks = response.data['plan']['weeks']
        self.assertEqual([w['number'] for w in weeks], [2, 3])
        self.assertEqual(weeks[0]['topics'][0]['id'], first)
        self.assertEqual([o['text'] for o in weeks[0]['topics'][0]['objectives']], self.topic_payload['objectives'])
        self.assertEqual(response.data['plan']['summary'], {'total': 2, 'not_started': 2, 'partial': 0, 'covered': 0})
        next_term = Term.objects.create(session=self.session, name='second', start_date=date(2027,1,1), end_date=date(2027,4,1), is_current=True)
        self.assertIsNone(self.client.get('/api/curriculum/plans/', {**self.query, 'term': next_term.pk}).data['plan'])
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).data['plan']['weeks'][1]['topics'][0]['id'], second)

    def test_duplicates_and_noop_audit(self):
        topic = self.topic()
        self.assertEqual(self.client.post('/api/curriculum/plans/', self.topic_payload, format='json').status_code, 409)
        self.assertEqual(self.client.post('/api/curriculum/plans/', {**self.topic_payload, 'position': 2,
            'objectives': ['Same', 'Same']}, format='json').status_code, 400)
        self.assertEqual(CurriculumTopic.objects.count(), 1)
        self.assertEqual(LearningObjective.objects.count(), 2)
        count = PlatformEvent.objects.filter(action__startswith='curriculum.').count()
        self.assertEqual(self.client.patch(f'/api/curriculum/topics/{topic}/', {}, format='json').status_code, 200)
        self.assertEqual(PlatformEvent.objects.filter(action__startswith='curriculum.').count(), count)
        self.assertEqual(self.client.patch(f'/api/curriculum/topics/{topic}/', {'archived': True}, format='json').status_code, 200)
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).data['plan']['summary']['total'], 0)

    def test_admin_edits_archive_and_historical_lock(self):
        topic = self.topic()
        self.assertEqual(self.client.patch(f'/api/curriculum/topics/{topic}/', {'title': 'Whole fractions',
            'objectives': ['Name fractions']}, format='json').status_code, 200)
        self.assertEqual(list(LearningObjective.objects.filter(topic_id=topic).values_list('text', flat=True)), ['Name fractions'])
        lesson = self.lesson()
        self.assertEqual(self.coverage(lesson, topic).status_code, 201)
        self.assertEqual(self.client.patch(f'/api/curriculum/topics/{topic}/', {'title': 'Changed after teaching'}, format='json').status_code, 409)
        self.assertEqual(self.client.patch(f'/api/curriculum/topics/{topic}/', {'objectives': []}, format='json').status_code, 409)
        self.assertEqual(self.client.patch(f'/api/curriculum/topics/{topic}/', {'archived': True}, format='json').status_code, 200)
        self.assertEqual(TopicCoverage.objects.count(), 1)
        historical_plan = self.client.get('/api/curriculum/plans/', self.query).data['plan']
        self.assertEqual(historical_plan['weeks'][0]['topics'][0]['title'], 'Whole fractions')
        self.assertEqual(historical_plan['summary']['total'], 1)
        self.assertEqual(historical_plan['summary']['partial'], 1)

    def test_coverage_progress_multiple_lessons_and_topics(self):
        first = self.topic()
        second = self.topic(position=2, title='Decimals', objectives=[])
        lesson1 = self.lesson()
        self.assertEqual(self.coverage(lesson1, first).status_code, 201)
        self.assertEqual(self.coverage(lesson1, second, 'covered').status_code, 201)
        self.assertEqual(self.coverage(lesson1, first).status_code, 200)
        self.assertEqual(TopicCoverage.objects.count(), 2)
        summary = self.client.get('/api/curriculum/plans/', self.query).data['plan']['summary']
        self.assertEqual((summary['covered'], summary['partial']), (1, 1))
        period2 = Period.objects.create(school=self.school, name='P2', start_time=time(9), end_time=time(10), order_index=2)
        slot2 = TimetableEntry.objects.create(school=self.school, term=self.term, class_arm=self.arm,
            subject=self.subject, teacher=self.teacher, day_of_week='MON', period=period2)
        response = self.client.put(f'/api/timetable/lessons/{slot2.pk}/{self.day}/', {'outcome': 'delivered', 'revision': 0}, format='json')
        lesson2 = response.data['id']
        self.assertEqual(self.coverage(lesson2, first, 'covered').status_code, 201)
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).data['plan']['summary']['covered'], 2)
        self.assertEqual(self.coverage(lesson1, first, 'partial', revision=1).status_code, 200)
        progress = self.client.get('/api/curriculum/plans/', self.query).data['plan']
        self.assertEqual(progress['summary']['covered'], 2)
        self.assertEqual(progress['weeks'][0]['summary']['covered'], 2)
        self.assertEqual([e['lesson'] for e in progress['weeks'][0]['topics'][0]['evidence']], [lesson1, lesson2])

    def test_progress_is_per_arm_and_week_does_not_control_delivery(self):
        topic = self.topic(week=12)
        lesson = self.lesson()
        self.assertEqual(self.coverage(lesson, topic, 'covered').status_code, 201)
        other_arm = ClassArm.objects.create(school=self.school, class_level=self.level, name='B')
        other_query = {**self.query, 'class_arm': other_arm.pk}
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).data['plan']['summary']['covered'], 1)
        self.assertEqual(self.client.get('/api/curriculum/plans/', other_query).data['plan']['summary']['not_started'], 1)

    def test_correction_remove_and_outcome_guard(self):
        topic = self.topic()
        lesson = self.lesson()
        self.assertEqual(self.coverage(lesson, topic).status_code, 201)
        self.assertEqual(self.coverage(lesson, topic, 'covered', revision=0).status_code, 409)
        self.assertEqual(self.coverage(lesson, topic, 'covered', revision=1).status_code, 200)
        self.assertEqual(self.client.put(self.lesson_url, {'outcome': 'missed', 'revision': 1}, format='json').status_code, 409)
        self.assertEqual(self.client.put(self.lesson_url, {'outcome': 'cancelled', 'revision': 1}, format='json').status_code, 409)
        url = f'/api/curriculum/lessons/{lesson}/topics/{topic}/'
        self.assertEqual(self.client.delete(url, {'revision': 2}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(url, {'revision': 2}, format='json').status_code, 200)
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).data['plan']['summary']['not_started'], 1)
        self.assertEqual(self.client.put(self.lesson_url, {'outcome': 'missed', 'revision': 1}, format='json').status_code, 200)
        self.assertEqual(self.coverage(lesson, topic, 'covered', revision=3).status_code, 409)
        self.assertEqual(TopicCoverage.objects.get().active, False)

    def test_missed_cancelled_unresolved_and_substituted(self):
        topic = self.topic()
        self.assertEqual(self.coverage(999999, topic).status_code, 404)
        for outcome in ('missed', 'cancelled'):
            self.slot.delete()
            period = Period.objects.create(school=self.school, name=outcome, start_time=time(10 if outcome == 'missed' else 11), end_time=time(11 if outcome == 'missed' else 12), order_index=3 if outcome == 'missed' else 4)
            self.slot = TimetableEntry.objects.create(school=self.school, term=self.term, class_arm=self.arm,
                subject=self.subject, teacher=self.teacher, day_of_week='MON', period=period)
            self.lesson_url = f'/api/timetable/lessons/{self.slot.pk}/{self.day}/'
            lesson = self.lesson(outcome)
            self.assertEqual(self.coverage(lesson, topic).status_code, 409)
        self.slot.delete()
        period = Period.objects.create(school=self.school, name='P5', start_time=time(12), end_time=time(13), order_index=5)
        self.slot = TimetableEntry.objects.create(school=self.school, term=self.term, class_arm=self.arm,
            subject=self.subject, teacher=self.teacher, day_of_week='MON', period=period)
        self.lesson_url = f'/api/timetable/lessons/{self.slot.pk}/{self.day}/'
        self.assertEqual(self.client.get(f'/api/curriculum/lessons/{self.slot.pk}/').status_code, 404)
        lesson = self.lesson('substituted')
        self.client.force_authenticate(self.substitute)
        self.assertEqual(self.coverage(lesson, topic).status_code, 201)

    def test_teacher_scope_and_foreign_context(self):
        topic = self.topic()
        lesson = self.lesson()
        unrelated = CustomUser.objects.create_user(email='unrelated-curriculum@test.invalid', password='Example-12345!',
            school=self.school, role='teacher', must_change_password=False)
        StaffProfile.objects.create(school=self.school, user=unrelated)
        self.client.force_authenticate(unrelated)
        self.assertEqual(self.client.get('/api/curriculum/assignments/').data['assignments'], [])
        self.assertEqual(self.client.get(f'/api/curriculum/slots/{self.slot.pk}/').status_code, 403)
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).status_code, 403)
        self.assertEqual(self.client.get(f'/api/curriculum/lessons/{lesson}/').status_code, 404)
        self.assertEqual(self.coverage(lesson, topic).status_code, 404)
        self.assertEqual(self.client.post('/api/curriculum/plans/', self.topic_payload, format='json').status_code, 403)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(len(self.client.get('/api/curriculum/assignments/').data['assignments']), 1)
        self.assertEqual(self.client.get(f'/api/curriculum/slots/{self.slot.pk}/').data['plan']['weeks'][0]['topics'][0]['id'], topic)
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).status_code, 200)
        self.assertEqual(self.coverage(lesson, topic).status_code, 201)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).status_code, 403)
        self.assertEqual(self.coverage(lesson, topic).status_code, 403)

    def test_holiday_excludes_unrecorded_lesson_and_never_counts_coverage(self):
        self.topic()
        Holiday.objects.create(term=self.term, name='School closure', start_date=self.day, end_date=self.day, holiday_type='school')
        schedule = self.client.get(f'/api/timetable/lessons/?date={self.day}')
        self.assertEqual(schedule.data['lessons'], [])
        self.assertTrue(schedule.data['holiday'])
        self.assertEqual(self.client.put(self.lesson_url, {'outcome': 'delivered', 'revision': 0}, format='json').status_code, 400)
        scheme = self.client.get(f'/api/curriculum/slots/{self.slot.pk}/').data
        self.assertEqual(scheme['holidays'][0]['name'], 'School closure')
        self.assertEqual(scheme['plan']['summary']['not_started'], 1)
        self.assertEqual(TopicCoverage.objects.count(), 0)

    def test_cross_tenant_topic_and_scope_rejected(self):
        topic = self.topic()
        lesson = self.lesson()
        foreign_subject = Subject.objects.create(school=self.other, name='Foreign', code='FRG')
        self.assertEqual(self.client.post('/api/curriculum/plans/', {**self.topic_payload, 'subject': foreign_subject.pk, 'position': 2}, format='json').status_code, 400)
        self.assertEqual(self.client.get('/api/curriculum/plans/', {**self.query, 'class_level': self.foreign_level.pk}).status_code, 400)
        self.assertEqual(self.client.get('/api/curriculum/plans/', {**self.query, 'class_arm': 999999}).status_code, 400)
        foreign_arm = ClassArm.objects.create(school=self.other, class_level=self.foreign_level, name='A')
        foreign_session = self.session.__class__.objects.create(school=self.other, name='2026/27', start_date=self.session.start_date, end_date=self.session.end_date)
        foreign_term = Term.objects.create(session=foreign_session, name='first', start_date=self.term.start_date, end_date=self.term.end_date)
        foreign_plan = CurriculumPlan.objects.create(school=self.other, term=foreign_term, class_level=self.foreign_level, subject=foreign_subject)
        from .models import CurriculumWeek
        foreign_week = CurriculumWeek.objects.create(plan=foreign_plan, number=2)
        foreign_topic = CurriculumTopic.objects.create(week=foreign_week, title='Foreign topic', position=1)
        self.assertEqual(self.coverage(lesson, foreign_topic.pk).status_code, 400)
        self.assertEqual(self.client.patch(f'/api/curriculum/topics/{foreign_topic.pk}/', {'title': 'Tamper'}, format='json').status_code, 404)
        other_admin = CustomUser.objects.create_user(email='foreign-admin-curriculum@test.invalid', password='Example-12345!',
            school=self.other, role='school_admin', must_change_password=False)
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.other.slug)
        self.client.force_authenticate(other_admin)
        self.assertEqual(self.client.get(f'/api/curriculum/lessons/{lesson}/').status_code, 404)
        self.assertEqual(self.coverage(lesson, topic).status_code, 404)
        self.assertEqual(self.client.get('/api/curriculum/plans/', self.query).status_code, 400)

    def test_wrong_subject_level_term_and_timetable_change(self):
        topic = self.topic()
        lesson = self.lesson()
        other_subject = Subject.objects.create(school=self.school, name='English', code='ENG')
        other_level = ClassLevel.objects.create(school=self.school, name='JSS2')
        other_plan = CurriculumPlan.objects.create(school=self.school, term=self.term, class_level=other_level, subject=other_subject)
        from .models import CurriculumWeek
        wrong = CurriculumTopic.objects.create(week=CurriculumWeek.objects.create(plan=other_plan, number=1), title='Wrong', position=1)
        self.assertEqual(self.coverage(lesson, wrong.pk).status_code, 400)
        self.assertEqual(self.coverage(lesson, topic).status_code, 201)
        self.slot.subject = other_subject
        self.slot.save()
        self.slot.delete()
        self.assertEqual(self.client.get(f'/api/curriculum/lessons/{lesson}/').data['coverage'][topic]['state'], 'partial')

    def test_progress_query_count_is_bounded(self):
        self.topic()
        with CaptureQueriesContext(connection) as one:
            self.client.get('/api/curriculum/plans/', self.query)
        for number in range(2, 22):
            self.topic(position=number, title=f'Topic {number}', objectives=[])
        with CaptureQueriesContext(connection) as many:
            self.client.get('/api/curriculum/plans/', self.query)
        print(f'CURRICULUM_QUERY_COUNTS topics=1:{len(one)} topics=21:{len(many)}')
        self.assertLessEqual(len(many) - len(one), 2)


@skipUnless(connection.vendor == 'postgresql', 'PostgreSQL row-lock check')
class CurriculumPostgresRaceTests(TransactionTestCase):
    def test_simultaneous_first_coverage_saves_one_record_and_audit(self):
        from tenants.models import School
        from academics.models import AcademicSession
        from .models import CurriculumWeek
        school = School.objects.create(name='Coverage Race', slug='coverage-race', subdomain='coverage-race', subscription_plan='basic')
        admin = CustomUser.objects.create_user(email='coverage-race@test.invalid', password='Example-12345!',
            school=school, role='school_admin', must_change_password=False)
        session = AcademicSession.objects.create(school=school, name='2026/27', start_date=date(2026,9,1), end_date=date(2027,7,30))
        term = Term.objects.create(session=session, name='first', start_date=date(2026,9,1), end_date=date(2026,12,18))
        level = ClassLevel.objects.create(school=school, name='JSS1')
        arm = ClassArm.objects.create(school=school, class_level=level, name='A')
        subject = Subject.objects.create(school=school, name='Math', code='MATH')
        plan = CurriculumPlan.objects.create(school=school, term=term, class_level=level, subject=subject)
        topic = CurriculumTopic.objects.create(week=CurriculumWeek.objects.create(plan=plan, number=1), title='Numbers', position=1)
        lesson = LessonRecord.objects.create(school=school, slot_id=999, date=date(2026,9,21), term=term,
            term_name=str(term), class_arm_id_snapshot=arm.pk, class_name=arm.full_name,
            subject_id_snapshot=subject.pk, subject_name=subject.name, period_name='P1',
            period_start=time(8), period_end=time(9), scheduled_teacher_id=admin.pk,
            actual_teacher=admin, outcome='delivered', recorded_by=admin)
        barrier = Barrier(2)

        def save():
            close_old_connections()
            client = APIClient(HTTP_X_SCHOOL_SLUG=school.slug)
            client.force_authenticate(admin)
            barrier.wait(timeout=10)
            try:
                return client.put(f'/api/curriculum/lessons/{lesson.pk}/topics/{topic.pk}/',
                                  {'state': 'partial', 'revision': 0}, format='json').status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda _: save(), range(2)))
        self.assertEqual(sorted(statuses), [200, 201])
        self.assertEqual(TopicCoverage.objects.count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action='curriculum.coverage_saved').count(), 1)

    def test_outcome_correction_and_coverage_cannot_commit_contradiction(self):
        from tenants.models import School
        from academics.models import AcademicSession
        from .models import CurriculumWeek
        school = School.objects.create(name='Outcome Race', slug='outcome-race', subdomain='outcome-race', subscription_plan='basic')
        admin = CustomUser.objects.create_user(email='outcome-race@test.invalid', password='Example-12345!',
            school=school, role='school_admin', must_change_password=False)
        teacher = CustomUser.objects.create_user(email='outcome-race-teacher@test.invalid', password='Example-12345!',
            school=school, role='teacher', must_change_password=False)
        StaffProfile.objects.create(school=school, user=teacher)
        session = AcademicSession.objects.create(school=school, name='2026/27', start_date=date(2026,9,1), end_date=date(2027,7,30))
        term = Term.objects.create(session=session, name='first', start_date=date(2026,9,1), end_date=date(2026,12,18))
        level = ClassLevel.objects.create(school=school, name='JSS1')
        arm = ClassArm.objects.create(school=school, class_level=level, name='A')
        subject = Subject.objects.create(school=school, name='Math', code='MATH')
        plan = CurriculumPlan.objects.create(school=school, term=term, class_level=level, subject=subject)
        topic = CurriculumTopic.objects.create(week=CurriculumWeek.objects.create(plan=plan, number=1), title='Numbers', position=1)
        period = Period.objects.create(school=school, name='P1', start_time=time(8), end_time=time(9), order_index=1)
        slot = TimetableEntry.objects.create(school=school, term=term, class_arm=arm, subject=subject,
            teacher=teacher, day_of_week='MON', period=period)
        client = APIClient(HTTP_X_SCHOOL_SLUG=school.slug)
        client.force_authenticate(admin)
        response = client.put(f'/api/timetable/lessons/{slot.pk}/2026-09-21/',
                              {'outcome': 'delivered', 'revision': 0}, format='json')
        lesson = response.data['id']
        barrier = Barrier(2)

        def write(kind):
            close_old_connections()
            local = APIClient(HTTP_X_SCHOOL_SLUG=school.slug)
            local.force_authenticate(admin)
            barrier.wait(timeout=10)
            try:
                if kind == 'coverage':
                    return local.put(f'/api/curriculum/lessons/{lesson}/topics/{topic.pk}/',
                                     {'state': 'covered', 'revision': 0}, format='json').status_code
                return local.put(f'/api/timetable/lessons/{slot.pk}/2026-09-21/',
                                 {'outcome': 'missed', 'revision': 1}, format='json').status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(write, ('coverage', 'outcome')))
        self.assertIn(409, statuses)
        lesson_record = LessonRecord.objects.get(pk=lesson)
        active = TopicCoverage.objects.filter(lesson=lesson_record, active=True).exists()
        self.assertFalse(active and lesson_record.outcome == 'missed')
