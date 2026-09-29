from datetime import date, time
from unittest.mock import patch

from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import CustomUser
from academics.models import AcademicSession, Holiday, Term
from attendance.models import AttendanceRecord, AttendanceSession
from curriculum.models import (
    AcademicResource, CurriculumPlan, CurriculumTopic, CurriculumWeek,
    LessonPlan, TopicCoverage,
)
from enrollment import test_operations as operations
from enrollment.models import ClassArm, StudentProfile
from fees.models import FeeCategory, FeePayment, FeeSchedule
from timetable.models import LessonRecord, Period, TimetableEntry


class PrincipalOperationsTests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)
    day = date(2026, 9, 21)

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)
        self.period = Period.objects.create(school=self.school, name='First', start_time=time(8), end_time=time(9), order_index=1)
        self.slot = TimetableEntry.objects.create(school=self.school, term=self.term, class_arm=self.arm,
            subject=self.subject, teacher=self.teacher, day_of_week='MON', period=self.period)

    def read(self, section, **kwargs):
        with patch('analytics.principal.timezone.localdate', return_value=self.day):
            return self.client.get('/api/principal/', {'section': section, 'date': str(self.day),
                'term': self.term.pk, **kwargs})

    def test_basic_snapshot_and_tenant_role_boundary(self):
        response = self.read('snapshot')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual((response.data['active_students'], response.data['active_teachers']), (1, 1))
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.read('snapshot').status_code, 403)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.read('snapshot').status_code, 403)
        parent = self.user('principal-parent', 'parent')
        self.client.force_authenticate(parent)
        self.assertEqual(self.read('snapshot').status_code, 403)
        foreign = CustomUser.objects.create_user(email='foreign-principal@operations.test', password='Test-password-26!',
            role='school_admin', school=self.other, must_change_password=False)
        self.client.force_authenticate(foreign)
        self.assertEqual(self.read('snapshot').status_code, 403)
        self.client.force_authenticate(self.admin)
        platform = CustomUser.objects.create_user(email='platform-principal@operations.test', password='Test-password-26!',
            role='superadmin', must_change_password=False)
        self.client.force_authenticate(platform)
        self.assertEqual(self.read('snapshot').status_code, 403)
        self.client.force_authenticate(self.admin)
        foreign_session = AcademicSession.objects.create(school=self.other, name='2026/27',
            start_date=date(2026, 9, 1), end_date=date(2027, 7, 30))
        foreign_term = Term.objects.create(session=foreign_session, name='first',
            start_date=date(2026, 9, 1), end_date=date(2026, 12, 18))
        self.assertEqual(self.client.get('/api/principal/', {'section': 'results', 'term': foreign_term.pk}).status_code, 400)
        self.assertEqual(self.client.get('/api/principal/', {'section': 'results', 'term': 999999}).status_code, 400)
        self.assertEqual(self.client.get('/api/principal/', {'section': 'teaching', 'date': 'bad'}).status_code, 400)
        foreign_student = CustomUser.objects.create_user(email='foreign-student@operations.test', password='Test-password-26!',
            role='student', school=self.other, must_change_password=False)
        StudentProfile.objects.create(school=self.other, user=foreign_student)
        injected = self.client.get('/api/principal/', {'section': 'snapshot', 'date': str(self.day), 'school': self.other.pk})
        self.assertEqual(injected.data['active_students'], 1)

    def test_unfinalized_attendance_is_not_reported_as_present(self):
        session = AttendanceSession.objects.create(school=self.school, class_arm=self.arm, teacher=self.teacher,
            term=self.term, date=self.day)
        AttendanceRecord.objects.create(attendance_session=session, student=self.student, status='present')
        first = self.read('attendance').data
        self.assertEqual(first['state'], 'no_records')
        self.assertEqual(first['marks']['present'], 0)
        self.assertEqual(first['classes_with_records'], 0)
        self.assertEqual(first['classes_expected'], 1)
        AttendanceRecord.objects.filter(attendance_session=session).update(status='absent')
        session.is_finalized = True
        session.save(update_fields=['is_finalized'])
        second = self.read('attendance').data
        self.assertEqual(second['marks']['present'], 0)
        self.assertEqual(second['marks']['absent'], 1)
        self.assertEqual(second['classes_with_records'], 1)
        self.assertEqual(second['examples']['absent'][0]['student__student_profile__id'], self.profile.pk)

    def test_lesson_unresolved_differs_from_missed_and_holiday_suppresses(self):
        teaching = self.read('teaching').data
        self.assertEqual(teaching['scheduled'], 1)
        self.assertEqual(teaching['counts']['unresolved'], 1)
        self.assertEqual(teaching['counts']['missed'], 0)
        saved = self.client.put(f'/api/timetable/lessons/{self.slot.pk}/{self.day}/',
            {'outcome': 'delivered', 'revision': 0}, format='json')
        self.assertEqual(saved.status_code, 201, saved.data)
        self.assertEqual(self.read('teaching').data['counts']['delivered'], 1)
        Holiday.objects.create(term=self.term, name='School closed', start_date=self.day, end_date=self.day)
        self.assertEqual(self.read('teaching').data['state'], 'non_teaching')
        self.assertEqual(self.read('attendance').data['state'], 'non_teaching')

    def test_results_and_finance_use_real_term_records(self):
        self.score.review_state = 'submitted'
        self.score.save(update_fields=['review_state'])
        result = self.read('results').data
        self.assertEqual(result['counts']['submitted'], 1)
        self.assertEqual(result['groups'][0]['class_arm'], self.arm.pk)
        category = FeeCategory.objects.create(school=self.school, name='Tuition')
        schedule = FeeSchedule.objects.create(school=self.school, term=self.term, class_level=self.level,
            fee_category=category, amount=1000)
        FeePayment.objects.create(school=self.school, student=self.profile, fee_schedule=schedule,
            amount_paid=250, payment_date=self.day, method='cash')
        finance = self.read('finance').data
        self.assertEqual(finance['recorded_payments'], 1)
        self.assertEqual(finance['recorded_amount'], '250.00')

    def test_curriculum_counts_only_explicit_coverage_and_no_other_school(self):
        plan = CurriculumPlan.objects.create(school=self.school, term=self.term, class_level=self.level, subject=self.subject)
        week = CurriculumWeek.objects.create(plan=plan, number=1)
        CurriculumTopic.objects.create(week=week, title='Uncovered', position=1)
        covered = CurriculumTopic.objects.create(week=week, title='Covered', position=2)
        lesson = LessonRecord.objects.create(school=self.school, slot_id=self.slot.pk, date=self.day, term=self.term,
            term_name=str(self.term), class_arm_id_snapshot=self.arm.pk, class_name=self.arm.full_name,
            subject_id_snapshot=self.subject.pk, subject_name=self.subject.name, period_name='First',
            period_start=time(8), period_end=time(9), scheduled_teacher_id=self.teacher.pk,
            actual_teacher=self.teacher, outcome='delivered', recorded_by=self.admin)
        TopicCoverage.objects.create(school=self.school, lesson=lesson, topic=covered, state='covered', recorded_by=self.admin)
        data = self.read('curriculum').data
        self.assertEqual(data['groups'][0]['planned'], 2)
        self.assertEqual(data['groups'][0]['covered'], 1)
        self.assertEqual(data['groups'][0]['not_started'], 1)
        foreign = self.other
        self.assertNotIn(foreign.pk, [row['class_arm'] for row in data['groups']])

    def test_academic_management_distinguishes_planning_from_delivery(self):
        plan = CurriculumPlan.objects.create(school=self.school, term=self.term, class_level=self.level, subject=self.subject)
        week = CurriculumWeek.objects.create(plan=plan, number=1)
        topic = CurriculumTopic.objects.create(week=week, title='Whole Numbers', position=1)
        LessonPlan.objects.create(
            school=self.school, term=self.term, class_arm=self.arm, subject=self.subject,
            curriculum_topic=topic, teacher=self.teacher, title='Whole Numbers plan', status='submitted'
        )
        AcademicResource.objects.create(
            school=self.school, class_level=self.level, subject=self.subject,
            title='Whole Numbers note', kind='note', status='reviewed', created_by=self.teacher
        )
        data = self.read('academic_management').data
        self.assertEqual(data['lesson_plan_counts']['submitted'], 1)
        self.assertEqual(data['resource_counts']['reviewed'], 1)
        self.assertEqual(data['groups'][0]['lesson_outcomes'], {})
        self.assertEqual(data['groups'][0]['covered_evidence_rows'], 0)
        self.assertIn('LessonRecord', data['note'])
        self.assertIn('TopicCoverage', data['note'])


    def test_academic_history_compares_same_term_across_sessions_from_recorded_evidence(self):
        current_plan = CurriculumPlan.objects.create(
            school=self.school, term=self.term, class_level=self.level, subject=self.subject
        )
        current_week = CurriculumWeek.objects.create(plan=current_plan, number=1)
        current_topic = CurriculumTopic.objects.create(week=current_week, title='Current topic', position=1)

        previous_session = AcademicSession.objects.create(
            school=self.school, name='2025/26',
            start_date=date(2025, 9, 1), end_date=date(2026, 7, 31)
        )
        previous_term = Term.objects.create(
            session=previous_session, name=self.term.name,
            start_date=date(2025, 9, 1), end_date=date(2025, 12, 18)
        )
        previous_plan = CurriculumPlan.objects.create(
            school=self.school, term=previous_term, class_level=self.level, subject=self.subject
        )
        previous_week = CurriculumWeek.objects.create(plan=previous_plan, number=1)
        previous_topic = CurriculumTopic.objects.create(week=previous_week, title='Previous topic', position=1)
        CurriculumTopic.objects.create(week=previous_week, title='Previous extra topic', position=2)

        current_lesson = LessonRecord.objects.create(
            school=self.school, slot_id=1001, date=self.day, term=self.term,
            term_name=str(self.term), class_arm_id_snapshot=self.arm.pk, class_name=self.arm.full_name,
            subject_id_snapshot=self.subject.pk, subject_name=self.subject.name, period_name='First',
            period_start=time(8), period_end=time(9), scheduled_teacher_id=self.teacher.pk,
            actual_teacher=self.teacher, outcome='delivered', recorded_by=self.admin
        )
        TopicCoverage.objects.create(
            school=self.school, lesson=current_lesson, topic=current_topic,
            state='covered', recorded_by=self.admin
        )
        previous_lesson = LessonRecord.objects.create(
            school=self.school, slot_id=1002, date=date(2025, 9, 22), term=previous_term,
            term_name=str(previous_term), class_arm_id_snapshot=self.arm.pk, class_name=self.arm.full_name,
            subject_id_snapshot=self.subject.pk, subject_name=self.subject.name, period_name='First',
            period_start=time(8), period_end=time(9), scheduled_teacher_id=self.teacher.pk,
            actual_teacher=self.teacher, outcome='missed', recorded_by=self.admin
        )
        TopicCoverage.objects.create(
            school=self.school, lesson=previous_lesson, topic=previous_topic,
            state='partial', recorded_by=self.admin
        )

        data = self.read('academic_history').data
        self.assertEqual(data['state'], 'comparable')
        self.assertEqual(data['previous']['session_name'], '2025/26')
        row = data['comparison'][0]
        self.assertEqual(row['current']['planned_topics'], 1)
        self.assertEqual(row['current']['covered_topics'], 1)
        self.assertEqual(row['current']['lesson_outcomes']['delivered'], 1)
        self.assertEqual(row['previous']['planned_topics'], 2)
        self.assertEqual(row['previous']['partial_topics'], 1)
        self.assertEqual(row['previous']['lesson_outcomes']['missed'], 1)
        self.assertIn('not teacher-quality', data['note'])

    def test_curriculum_query_count_does_not_grow_per_topic(self):
        plan = CurriculumPlan.objects.create(school=self.school, term=self.term, class_level=self.level, subject=self.subject)
        week = CurriculumWeek.objects.create(plan=plan, number=1)
        CurriculumTopic.objects.create(week=week, title='First', position=1)
        with CaptureQueriesContext(connection) as baseline:
            first = self.read('curriculum')
        self.assertEqual(first.status_code, 200)
        CurriculumTopic.objects.bulk_create([
            CurriculumTopic(week=week, title=f'Topic {index}', position=index)
            for index in range(2, 32)
        ])
        with CaptureQueriesContext(connection) as expanded:
            second = self.read('curriculum')
        self.assertEqual(second.data['groups'][0]['planned'], 31)
        self.assertLessEqual(len(expanded), len(baseline) + 1)

    def test_section_query_budget_stays_bounded_as_school_grows(self):
        plan = CurriculumPlan.objects.create(school=self.school, term=self.term, class_level=self.level, subject=self.subject)
        week = CurriculumWeek.objects.create(plan=plan, number=1)
        CurriculumTopic.objects.create(week=week, title='First', position=1)
        sections = ('snapshot', 'attendance', 'teaching', 'curriculum', 'results', 'finance')
        def counts():
            result = {}
            for section in sections:
                with CaptureQueriesContext(connection) as queries:
                    response = self.read(section)
                self.assertEqual(response.status_code, 200, response.content)
                result[section] = len(queries)
            return result
        baseline = counts()
        for index in range(5):
            user = self.user(f'principal-student-{index}', 'student')
            StudentProfile.objects.create(school=self.school, user=user, current_class=self.arm)
        for index in range(2):
            ClassArm.objects.create(school=self.school, class_level=self.level, name=f'B{index}')
        CurriculumTopic.objects.bulk_create([CurriculumTopic(week=week, title=f'Extra {index}', position=index)
                                             for index in range(2, 22)])
        expanded = counts()
        for section in sections:
            self.assertLessEqual(expanded[section], baseline[section] + 2, (section, baseline, expanded))
        print(f'PRINCIPAL_QUERY_COUNTS baseline={baseline} expanded={expanded}')
