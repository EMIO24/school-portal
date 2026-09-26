from contextlib import redirect_stdout
from decimal import Decimal
from io import StringIO
from time import perf_counter

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import CustomUser, ParentStudentLink
from academics.models import Term
from attendance.models import AttendanceRecord, AttendanceSession
from enrollment.models import ClassArm, StaffProfile, StudentProfile, Subject, SubjectAssignment
from fees.models import FeePayment, FeeSchedule, TermInvoice
from gradebook.models import ScoreEntry, TermScoring
from tenants.models import School


class CommercialSimulationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seed_output = StringIO()
        with redirect_stdout(cls.seed_output):
            call_command('seed_commercial_simulation', confirm_development=True)
        cls.school = School.objects.get(slug='paideia-simulation')
        cls.other = School.objects.get(slug='paideia-boundary')
        cls.admin = CustomUser.objects.filter(school=cls.school, role='school_admin').order_by('id').first()
        cls.term = Term.objects.get(session__school=cls.school, is_current=True)
        cls.client = None

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def test_repeatable_dataset_counts_and_immutable_500_student_invoice(self):
        self.assertEqual(StudentProfile.objects.filter(school=self.school).count(), 505)
        self.assertEqual(StudentProfile.objects.filter(school=self.school, status='active').count(), 500)
        self.assertEqual(StaffProfile.objects.filter(school=self.school).count(), 40)
        self.assertEqual(StaffProfile.objects.filter(school=self.school, user__role='teacher').count(), 25)
        self.assertEqual(CustomUser.objects.filter(school=self.school, role='parent').count(), 380)
        self.assertEqual(ClassArm.objects.filter(school=self.school).count(), 18)
        self.assertEqual(Subject.objects.filter(school=self.school).count(), 15)
        self.assertEqual(SubjectAssignment.objects.filter(school=self.school).count(), 91)
        self.assertEqual(AttendanceSession.objects.filter(school=self.school).count(), 90)
        self.assertEqual(AttendanceRecord.objects.filter(attendance_session__school=self.school).count(), 2500)
        self.assertEqual(FeeSchedule.objects.filter(school=self.school).count(), 18)
        self.assertEqual(FeePayment.objects.filter(school=self.school).count(), 300)
        self.assertGreater(ScoreEntry.objects.filter(school=self.school).count(), 120)
        self.assertTrue(ParentStudentLink.objects.filter(school=self.school, parent__child_links__school=self.school).exists())
        invoice = TermInvoice.objects.get(school=self.school, term=self.term)
        self.assertEqual(invoice.active_student_count, 500)
        self.assertEqual(invoice.standard_rate, Decimal('800'))
        self.assertEqual(invoice.effective_rate, Decimal('720'))
        self.assertEqual(invoice.final_amount, Decimal('360000'))
        active_pk = StudentProfile.objects.filter(school=self.school, status='active').order_by('id').values_list('pk', flat=True).first()
        StudentProfile.objects.filter(pk=active_pk).update(status='withdrawn')
        invoice.refresh_from_db()
        self.assertEqual((invoice.active_student_count, invoice.final_amount), (500, Decimal('360000')))
        with self.assertRaises(CommandError):
            call_command('seed_commercial_simulation', confirm_development=True)

    def test_teacher_attendance_and_result_lifecycle_preserve_history(self):
        draft = ScoreEntry.objects.filter(school=self.school, term=self.term, review_state='draft').first()
        assignment = SubjectAssignment.objects.select_related('teacher__user').get(
            school=self.school, term=self.term, class_arm=draft.class_arm, subject=draft.subject,
        )
        teacher = assignment.teacher.user
        self.client.force_authenticate(teacher)
        historical = ScoreEntry.objects.filter(school=self.school, is_published=True).exclude(term=self.term).first()
        historical_snapshot = (historical.total_score, historical.grade, historical.is_published)

        start = self.client.post('/api/attendance/sessions/start/', {
            'class_arm': assignment.class_arm_id, 'term': self.term.pk,
            'date': '2026-09-20', 'mode': 'daily',
        }, format='json')
        self.assertEqual(start.status_code, 201, start.data)
        attendance_id = start.data['id']
        expected = StudentProfile.objects.filter(
            school=self.school, current_class_id=assignment.class_arm_id, status='active'
        ).count()
        self.assertEqual(len(start.data['records']), expected)
        self.assertFalse(AttendanceRecord.objects.filter(
            attendance_session_id=attendance_id, student__student_profile__status='withdrawn'
        ).exists())
        payload = {'records': [
            {'student_id': row['student'], 'status': 'late' if i == 0 else 'present'}
            for i, row in enumerate(start.data['records'])
        ]}
        for _ in range(2):
            self.assertEqual(self.client.patch(
                f'/api/attendance/sessions/{attendance_id}/submit/', payload, format='json'
            ).status_code, 200)
        self.assertEqual(AttendanceRecord.objects.filter(attendance_session_id=attendance_id).count(), expected)

        sheet_url = (
            f'/api/gradebook/entries/sheet/?class_arm={assignment.class_arm_id}'
            f'&subject={assignment.subject_id}&term={self.term.pk}'
        )
        before = self.client.get(sheet_url)
        self.assertEqual(before.status_code, 200)
        self.assertEqual(len(before.data['students']), expected)
        lifecycle = (
            f'?class_arm={assignment.class_arm_id}&subject={assignment.subject_id}&term={self.term.pk}'
        )
        self.assertEqual(self.client.post('/api/gradebook/entries/submit/' + lifecycle).status_code, 200)
        self.assertEqual(self.client.get(sheet_url).status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post('/api/gradebook/entries/approve/' + lifecycle).status_code, 200)
        self.assertEqual(self.client.post('/api/gradebook/entries/publish/' + lifecycle).status_code, 200)
        historical.refresh_from_db()
        self.assertEqual((historical.total_score, historical.grade, historical.is_published), historical_snapshot)
        scoring = TermScoring.objects.get(school=self.school, term=self.term)
        scoring.components = list(scoring.components)
        with self.assertRaises(Exception):
            scoring.save()

    def test_parent_student_role_and_tenant_boundaries(self):
        foreign_profile = StudentProfile.objects.get(school=self.other)
        foreign_staff = StaffProfile.objects.get(school=self.other)
        foreign_assignment = SubjectAssignment.objects.get(school=self.other)
        foreign_attendance = AttendanceSession.objects.get(school=self.other)
        foreign_score = ScoreEntry.objects.get(school=self.other)
        foreign_payment = FeePayment.objects.get(school=self.other)
        foreign_invoice = TermInvoice.objects.get(school=self.other)
        protected = [
            f'/api/students/{foreign_profile.pk}/', f'/api/staff/{foreign_staff.pk}/',
            f'/api/subject-assignments/{foreign_assignment.pk}/',
            f'/api/attendance/sessions/{foreign_attendance.pk}/',
            f'/api/gradebook/entries/{foreign_score.pk}/',
            f'/api/fees/student/{foreign_profile.pk}/', f'/api/fees/receipts/{foreign_payment.pk}/',
            f'/api/fees/subscription/invoices/{foreign_invoice.pk}/',
        ]
        for url in protected:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        count = FeePayment.objects.count()
        response = self.client.post('/api/fees/pay/manual/', {
            'student_id': foreign_profile.pk, 'fee_schedule_id': foreign_payment.fee_schedule_id,
            'amount_paid': '100', 'payment_date': '2026-09-26', 'method': 'cash',
        }, format='json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(FeePayment.objects.count(), count)

        published = ScoreEntry.objects.filter(school=self.school, term=self.term, is_published=True).first()
        profile = published.student.student_profile
        parent = ParentStudentLink.objects.filter(school=self.school, student=profile).first().parent
        self.client.force_authenticate(parent)
        self.assertEqual(self.client.get('/api/parent/children/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/results/slip-data/{published.student_id}/?term={self.term.pk}').status_code, 200)
        unrelated = StudentProfile.objects.filter(school=self.school).exclude(parent_links__parent=parent).first()
        self.assertIn(self.client.get(
            f'/api/results/slip-data/{unrelated.user_id}/?term={self.term.pk}'
        ).status_code, (403, 404))
        self.assertEqual(self.client.get('/api/students/').status_code, 403)
        self.client.force_authenticate(published.student)
        self.assertEqual(self.client.get(f'/api/results/slip-data/{published.student_id}/?term={self.term.pk}').status_code, 200)
        self.assertIn(self.client.get(
            f'/api/results/slip-data/{unrelated.user_id}/?term={self.term.pk}'
        ).status_code, (403, 404))

    def test_manual_payment_retry_is_idempotent(self):
        student = StudentProfile.objects.filter(school=self.school, status='active').order_by('id')[350]
        schedule = FeeSchedule.objects.filter(
            school=self.school, term=self.term, class_level=student.current_class.class_level,
        ).first()
        payload = {
            'student_id': student.pk, 'fee_schedule_id': schedule.pk, 'amount_paid': '1000.00',
            'payment_date': '2026-09-26', 'method': 'bank_transfer',
            'idempotency_key': 'simulation-payment-retry-001',
        }
        before = FeePayment.objects.count()
        first = self.client.post('/api/fees/pay/manual/', payload, format='json')
        second = self.client.post('/api/fees/pay/manual/', payload, format='json')
        self.assertEqual((first.status_code, second.status_code), (201, 200))
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(FeePayment.objects.count(), before + 1)
        self.assertEqual(self.client.post(
            '/api/fees/pay/manual/', {**payload, 'amount_paid': '2000.00'}, format='json'
        ).status_code, 409)

    def test_representative_endpoint_query_counts_are_bounded(self):
        assignment = SubjectAssignment.objects.filter(school=self.school, term=self.term).first()
        published = ScoreEntry.objects.filter(school=self.school, term=self.term, is_published=True).first()
        parent = ParentStudentLink.objects.filter(school=self.school, student__user=published.student).first().parent
        endpoints = [
            ('students', '/api/students/', self.admin, 6),
            ('staff', '/api/staff/', self.admin, 7),
            ('assignments', '/api/subject-assignments/?page=1', self.admin, 5),
            ('attendance', f'/api/attendance/sessions/class-report/?class_arm={assignment.class_arm_id}&term={self.term.pk}', self.admin, 5),
            ('gradebook', f'/api/gradebook/entries/sheet/?class_arm={assignment.class_arm_id}&subject={assignment.subject_id}&term={self.term.pk}', self.admin, 9),
            ('results', f'/api/results/class-results/?class_arm={published.class_arm_id}&term={self.term.pk}', self.admin, 5),
            ('debtors', f'/api/fees/outstanding/?term={self.term.pk}', self.admin, 7),
            ('low_attendance', f'/api/attendance/sessions/low-attendance/?term={self.term.pk}&threshold=95', self.admin, 5),
            ('parent_children', '/api/parent/children/', parent, 5),
            ('parent_dashboard', f'/api/parent/dashboard/{published.student.student_profile.pk}/', parent, 16),
        ]
        observations = []
        for name, url, user, ceiling in endpoints:
            self.client.force_authenticate(user)
            started = perf_counter()
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(url)
            elapsed_ms = (perf_counter() - started) * 1000
            self.assertEqual(response.status_code, 200, (name, getattr(response, 'data', None)))
            self.assertLessEqual(len(queries), ceiling, (name, len(queries)))
            data = response.data
            rows = len(data.get('results', data.get('students', []))) if isinstance(data, dict) else len(data)
            observations.append(f'{name}:{len(queries)}q/{rows}rows/{elapsed_ms:.1f}ms')
        print('COMMERCIAL_SIMULATION_PERFORMANCE ' + ' '.join(observations))
