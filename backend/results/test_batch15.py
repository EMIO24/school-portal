"""Release-focused report and public result access regressions."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch
from django.apps import apps
from django.contrib.auth.hashers import make_password
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from accounts.models import ParentStudentLink
from attendance.models import AttendanceRecord, AttendanceSession
from enrollment import test_operations as operations
from enrollment.models import ClassArm, Subject
from gradebook.models import ScoreEntry
from .models import ScratchCard, PublishedReportStyle, ResultRemark
from .presentation import capture_presentation


class ReportAccessTests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)

    def test_config_preview_and_published_snapshot_stay_separate(self):
        url = '/api/results/report-configuration/'
        self.assertEqual(self.client.patch(url, {'layout': 'script'}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(url, {
            'layout': 'modern', 'title': 'School Progress Report', 'show_position': False,
        }, format='json').status_code, 200)
        slip = f'/api/results/slip-data/{self.student.pk}/?term={self.term.pk}'
        self.assertEqual(self.client.get(slip).status_code, 404)
        preview = self.client.get(slip + '&preview=1')
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['layout'], 'modern')
        self.assertTrue(preview.data['unpublished_preview'])
        capture_presentation(self.school, self.term)
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        self.client.patch(url, {'layout': 'compact'}, format='json')
        official = self.client.get(slip)
        self.assertEqual(official.data['layout'], 'modern')
        self.assertEqual(official.data['score_rows'][0]['grade'], self.score.grade)
        self.assertFalse(official.data['unpublished_preview'])
        self.assertEqual(PublishedReportStyle.objects.filter(term=self.term).count(), 1)
        self.client.force_authenticate(self.student)
        self.assertEqual(self.client.get(slip + '&preview=1').data['layout'], 'modern')
        self.assertEqual(self.client.patch(url, {'layout': 'classic'}, format='json').status_code, 403)

    def test_parent_student_and_foreign_school_access(self):
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        parent = self.user('linked-parent', 'parent')
        outsider = self.user('unlinked-parent', 'parent')
        ParentStudentLink.objects.create(school=self.school, parent=parent, student=self.profile)
        slip = f'/api/results/slip-data/{self.student.pk}/?term={self.term.pk}'
        for user, expected in [(self.student, 200), (parent, 200), (outsider, 403)]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(slip).status_code, expected)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(slip, HTTP_X_SCHOOL_SLUG=self.other.slug).status_code, 403)

    def test_positions_reject_incomplete_publication(self):
        url = f'/api/results/positions/compute/?class_arm={self.arm.pk}&term={self.term.pk}'
        self.assertEqual(self.client.post(url).status_code, 409)
        self.assertEqual(self.client.get(f'/api/results/slip-data/{self.student.pk}/?term={self.term.pk}').status_code, 404)
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        self.assertEqual(self.client.post(url).status_code, 200)

    def test_upgrade_snapshot_preserves_existing_published_term(self):
        import importlib
        migration = importlib.import_module('results.migrations.0004_snapshot_existing_published_reports')
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        migration.snapshot_existing(apps, SimpleNamespace(connection=connection))
        snapshot = PublishedReportStyle.objects.get(term=self.term)
        self.assertEqual(snapshot.configuration['layout'], 'classic')
        self.assertEqual(snapshot.branding['school_name'], self.school.name)
        self.client.patch('/api/results/report-configuration/', {'layout': 'modern'}, format='json')
        self.assertEqual(self.client.get(
            f'/api/results/slip-data/{self.student.pk}/?term={self.term.pk}').data['layout'], 'classic')

    def test_pdf_fallback_keeps_authoritative_scores(self):
        from .views import _assemble_slip_data, _render_pdf
        from django.template.loader import render_to_string
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        context = _assemble_slip_data(self.school, self.student, self.term)
        html = render_to_string('result_slip.html', context)
        self.assertIn('Math', html)
        self.assertIn('Not calculated', html)
        with patch('results.views.render_to_string', side_effect=RuntimeError('native PDF unavailable')):
            pdf = _render_pdf('result_slip.html', context)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertIn(b'Math', pdf)
        self.assertIn(context['score_rows'][0]['grade'].encode(), pdf)

    def test_historical_class_and_attendance_exclude_other_classes(self):
        from datetime import date
        from .views import _assemble_slip_data
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        other_arm = ClassArm.objects.create(school=self.school, class_level=self.level, name='B')
        own_day = AttendanceSession.objects.create(
            school=self.school, class_arm=self.arm, term=self.term,
            date=date(2026, 9, 2), is_finalized=True,
        )
        AttendanceRecord.objects.create(attendance_session=own_day, student=self.student, status='present')
        other_day = AttendanceSession.objects.create(
            school=self.school, class_arm=other_arm, term=self.term,
            date=date(2026, 9, 2), is_finalized=True,
        )
        AttendanceRecord.objects.create(attendance_session=other_day, student=self.student, status='present')
        unfinalized = AttendanceSession.objects.create(
            school=self.school, class_arm=self.arm, term=self.term,
            date=date(2026, 9, 3), is_finalized=False,
        )
        AttendanceRecord.objects.create(attendance_session=unfinalized, student=self.student, status='absent')
        self.profile.current_class = other_arm
        self.profile.save(update_fields=['current_class'])
        report = _assemble_slip_data(self.school, self.student, self.term)
        self.assertEqual(report['class_name'], str(self.arm))
        self.assertEqual(report['total_days'], 1)
        self.assertEqual(report['days_present'], 1)

    def test_class_zip_contains_only_published_historical_class_results(self):
        import io
        import zipfile
        url = f'/api/results/all-slips/{self.arm.pk}/?term={self.term.pk}'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        moved_to = ClassArm.objects.create(school=self.school, class_level=self.level, name='B')
        self.profile.current_class = moved_to
        self.profile.save(update_fields=['current_class'])
        with patch('results.views._render_pdf', return_value=b'%PDF-fixture'):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            self.assertEqual(len(archive.namelist()), 1)
            self.assertEqual(archive.read(archive.namelist()[0]), b'%PDF-fixture')

    def test_partially_reopened_result_cannot_be_exported_or_redeemed(self):
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        second = Subject.objects.create(school=self.school, name='English', code='ENG')
        ScoreEntry.objects.create(
            school=self.school, student=self.student, class_arm=self.arm,
            subject=second, session=self.session, term=self.term, exam_score=45,
        )
        ResultRemark.objects.create(
            school=self.school, student=self.student, class_arm=self.arm, term=self.term,
            total_score=self.score.total_score, subjects_offered=1,
        )
        self.assertEqual(self.client.get(
            f'/api/results/slip-data/{self.student.pk}/?term={self.term.pk}').status_code, 404)
        self.assertEqual(self.client.get(
            f'/api/results/all-slips/{self.arm.pk}/?term={self.term.pk}').status_code, 404)
        self.assertEqual(self.client.get(
            f'/api/results/broadsheet/{self.arm.pk}/?term={self.term.pk}').status_code, 409)
        self.school.subscription_plan = 'premium'
        self.school.save(update_fields=['subscription_plan'])
        card = ScratchCard.objects.create(school=self.school, term=self.term,
            serial_number='BATCH15-PARTIAL-1', pin_hash=make_password('1234567890'))
        response = APIClient().post('/api/results/check/', {
            'admission_number': self.profile.admission_number,
            'serial_number': card.serial_number, 'pin': '1234567890',
        }, format='json')
        self.assertEqual(response.status_code, 403)
        card.refresh_from_db()
        self.assertFalse(card.is_used)

    def test_card_errors_revocation_and_bound_historical_term(self):
        self.school.subscription_plan = 'premium'
        self.school.save(update_fields=['subscription_plan'])
        card = ScratchCard.objects.create(school=self.school, term=self.term,
            serial_number='BATCH15-HISTORY-1', pin_hash=make_password('1234567890'), batch_name='Historical')
        public = APIClient()
        payload = {'admission_number': self.profile.admission_number,
                   'serial_number': card.serial_number, 'pin': '1234567890'}
        missing = public.post('/api/results/check/', {}, format='json')
        wrong = public.post('/api/results/check/', {**payload, 'pin': 'wrong'}, format='json')
        unpublished = public.post('/api/results/check/', payload, format='json')
        self.assertEqual((missing.status_code, wrong.status_code, unpublished.status_code), (403, 403, 403))
        self.assertEqual(missing.data, wrong.data)
        self.assertEqual(wrong.data, unpublished.data)
        self.assertEqual(public.post('/api/results/check/', {
            **payload, 'admission_number': 'NOT-THIS-STUDENT'}, format='json').data, wrong.data)
        self.assertFalse(ScratchCard.objects.get(pk=card.pk).is_used)
        self.assertEqual(self.client.post(f'/api/scratch-cards/{card.pk}/revoke/').status_code, 200)
        self.assertEqual(public.post('/api/results/check/', payload, format='json').status_code, 403)
        self.assertEqual(self.client.get('/api/scratch-cards/batch-stats/').data[0]['revoked'], 1)
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        second = ScratchCard.objects.create(school=self.school, term=self.term,
            serial_number='BATCH15-HISTORY-2', pin_hash=make_password('1234567890'), batch_name='Historical')
        payload['serial_number'] = second.serial_number
        response = public.post('/api/results/check/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['term_name'], self.term.name)
        self.assertEqual(public.post('/api/results/check/', payload, format='json').status_code, 403)


class CardConcurrencyTests(TransactionTestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)

    def test_one_postgresql_card_use(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL row-lock and conditional-update race')
        operations.BasicOperationsTests.setUpTestData.__func__(type(self))
        self.school.subscription_plan = 'premium'
        self.school.save(update_fields=['subscription_plan'])
        self.score.is_published = True
        self.score.save(update_fields=['is_published'])
        card = ScratchCard.objects.create(school=self.school, term=self.term,
            serial_number='BATCH15-RACE-1', pin_hash=make_password('1234567890'), batch_name='Race')
        payload = {'admission_number': self.profile.admission_number,
                   'serial_number': card.serial_number, 'pin': '1234567890'}
        def consume(_):
            close_old_connections()
            try:
                return APIClient().post('/api/results/check/', payload, format='json').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(consume, range(2))), [200, 403])
        card.refresh_from_db()
        self.assertTrue(card.is_used)
        self.assertEqual(card.used_by_student_id, self.student.pk)
