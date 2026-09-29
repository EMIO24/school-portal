from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from accounts.models import CustomUser, ParentStudentLink
from enrollment import test_operations as operations
from enrollment.models import ClassArm, StaffProfile, StudentProfile
from tenants.models import PlatformEvent
from .models import Communication, CommunicationRecipient


class CommunicationTests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)

    def setUp(self):
        self.client = APIClient(HTTP_X_SCHOOL_SLUG=self.school.slug)
        self.client.force_authenticate(self.admin)
        self.parent = self.user('linked-parent', 'parent')
        ParentStudentLink.objects.create(school=self.school, parent=self.parent, student=self.profile)
        self.sibling = self.user('sibling', 'student')
        self.sibling_profile = StudentProfile.objects.create(school=self.school, user=self.sibling, current_class=self.arm)
        ParentStudentLink.objects.create(school=self.school, parent=self.parent, student=self.sibling_profile)
        self.other_parent = self.user('unlinked-parent', 'parent')
        self.payload = {'title': 'Friday closing', 'body': 'School closes at 1 PM.',
                        'audience': 'class_parents', 'class_arm_id': self.arm.pk, 'channels': ['portal']}

    def send(self, payload=None, key='notice-1'):
        return self.client.post('/api/communications/send/', payload or self.payload,
                                format='json', HTTP_IDEMPOTENCY_KEY=key)

    def test_class_parent_preview_deduplicates_and_sent_snapshot_is_stable(self):
        preview = self.client.post('/api/communications/preview/', self.payload, format='json')
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data['recipient_count'], 1)
        response = self.send()
        self.assertEqual(response.status_code, 201, response.data)
        notice = Communication.objects.get()
        self.assertEqual(notice.recipient_count, 1)
        self.assertEqual(list(CommunicationRecipient.objects.values_list('user_id', flat=True)), [self.parent.pk])
        self.assertEqual(PlatformEvent.objects.filter(action='school.communication_published').count(), 1)
        ParentStudentLink.objects.filter(parent=self.parent).delete()
        self.profile.current_class = None
        self.profile.save(update_fields=['current_class'])
        self.assertEqual(self.send().status_code, 200)
        history = self.client.get(f'/api/communications/history/{notice.pk}/')
        self.assertEqual((history.data['recipient_count'], history.data['body']), (1, self.payload['body']))
        self.client.force_authenticate(self.parent)
        self.assertEqual(self.client.get('/api/communications/inbox/').data['count'], 1)

    def test_all_and_selected_parents_use_links_not_guardian_text(self):
        self.profile.guardian_email = self.other_parent.email
        self.profile.save(update_fields=['guardian_email'])
        for audience, extra in [('all_parents', {}), ('selected_parents', {'recipient_ids': [self.parent.pk]})]:
            with self.subTest(audience=audience):
                payload = {**self.payload, 'audience': audience, 'class_arm_id': None, **extra}
                payload.pop('class_arm_id')
                preview = self.client.post('/api/communications/preview/', payload, format='json')
                self.assertEqual(preview.data['recipient_count'], 1)
                self.assertEqual(self.send(payload, key=audience).status_code, 201)
        self.assertEqual(CommunicationRecipient.objects.filter(user=self.other_parent).count(), 0)
        bad = {**self.payload, 'audience': 'selected_parents', 'recipient_ids': [self.other_parent.pk]}
        bad.pop('class_arm_id')
        self.assertEqual(self.send(bad, key='bad-parent').status_code, 400)

    def test_staff_teacher_and_student_audiences(self):
        self.arm.class_teacher = self.teacher
        self.arm.save(update_fields=['class_teacher'])
        for audience, extra, count in [
            ('all_staff', {}, 1), ('class_teachers', {'class_arm_id': self.arm.pk}, 1),
            ('selected_staff', {'recipient_ids': [self.teacher.pk]}, 1),
            ('all_students', {}, 2), ('class_students', {'class_arm_id': self.arm.pk}, 2),
            ('selected_students', {'recipient_ids': [self.student.pk]}, 1),
        ]:
            payload = {'title': audience, 'body': 'A notice', 'audience': audience,
                       'channels': ['portal'], **extra}
            with self.subTest(audience=audience):
                preview = self.client.post('/api/communications/preview/', payload, format='json')
                self.assertEqual(preview.status_code, 200, preview.data)
                self.assertEqual(preview.data['recipient_count'], count)
                self.assertEqual(self.send(payload, key=audience).status_code, 201)
        self.client.force_authenticate(self.teacher)
        self.assertEqual(self.client.get('/api/communications/inbox/').data['count'], 3)
        self.client.force_authenticate(self.admin)
        self.arm.class_teacher = None
        self.arm.save(update_fields=['class_teacher'])
        preview = self.client.post('/api/communications/preview/',
            {'audience': 'class_teachers', 'class_arm_id': self.arm.pk}, format='json')
        self.assertEqual(preview.data['recipient_count'], 0)  # Historical term assignment is not current.

    def test_foreign_identifiers_and_roles_cannot_send_or_read(self):
        foreign_parent = CustomUser.objects.create_user(email='foreign-notice@example.test', password='Pass-123456!',
            role='parent', school=self.other, must_change_password=False)
        foreign_student = CustomUser.objects.create_user(email='foreign-student-notice@example.test', password='Pass-123456!',
            role='student', school=self.other, must_change_password=False)
        foreign_profile = StudentProfile.objects.create(school=self.other, user=foreign_student)
        foreign_arm = ClassArm.objects.create(school=self.other, class_level=self.foreign_level, name='B')
        foreign_teacher = CustomUser.objects.create_user(email='foreign-teacher-notice@example.test', password='Pass-123456!',
            role='teacher', school=self.other, must_change_password=False)
        StaffProfile.objects.create(school=self.other, user=foreign_teacher)
        for payload in [
            {**self.payload, 'class_arm_id': foreign_arm.pk},
            {'title': 'X', 'body': 'X', 'audience': 'selected_parents', 'recipient_ids': [foreign_parent.pk]},
            {'title': 'X', 'body': 'X', 'audience': 'selected_staff', 'recipient_ids': [foreign_teacher.pk]},
            {'title': 'X', 'body': 'X', 'audience': 'selected_students', 'recipient_ids': [foreign_student.pk]},
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post('/api/communications/preview/', payload, format='json').status_code, 400)
                self.assertEqual(self.send(payload, key='foreign-' + str(len(str(payload)))).status_code, 400)
        self.assertEqual(Communication.objects.count(), 0)
        notice_id = self.send().data['id']
        recipient_id = CommunicationRecipient.objects.get().pk
        for user in (self.teacher, self.student, self.parent, self.other_parent, foreign_parent):
            self.client.force_authenticate(user)
            self.assertEqual(self.send(key=f'forbidden-{user.pk}').status_code, 403)
        self.client.force_authenticate(self.other_parent)
        self.assertEqual(self.client.get('/api/communications/inbox/').data['count'], 0)
        self.assertEqual(self.client.post(f'/api/communications/inbox/{recipient_id}/read/').status_code, 404)
        self.client.force_authenticate(foreign_parent)
        self.assertEqual(self.client.get('/api/communications/inbox/').status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/communications/history/').data['count'], 1)
        other_client = APIClient(HTTP_X_SCHOOL_SLUG=self.other.slug)
        other_admin = CustomUser.objects.create_user(email='foreign-admin-notice@example.test', password='Pass-123456!',
            role='school_admin', school=self.other, must_change_password=False)
        other_client.force_authenticate(other_admin)
        self.assertEqual(other_client.get(f'/api/communications/history/{notice_id}/').status_code, 404)

    def test_idempotency_read_and_history_pagination(self):
        first = self.send()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(self.send().data['replayed'], True)
        self.assertEqual(self.send({**self.payload, 'body': 'Different'}, key='notice-1').status_code, 409)
        self.assertEqual(Communication.objects.count(), 1)
        self.assertEqual(CommunicationRecipient.objects.count(), 1)
        self.assertEqual(PlatformEvent.objects.filter(action='school.communication_published').count(), 1)
        self.client.force_authenticate(self.parent)
        inbox = self.client.get('/api/communications/inbox/')
        self.assertEqual(inbox.data['results'][0]['status'], 'available_in_portal')
        row_id = inbox.data['results'][0]['id']
        self.assertEqual(self.client.post(f'/api/communications/inbox/{row_id}/read/').data['status'], 'read')
        self.assertEqual(self.client.post(f'/api/communications/inbox/{row_id}/read/').status_code, 200)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get(f"/api/communications/history/{first.data['id']}/").data['read_count'], 1)
        for i in range(21):
            self.send(key=f'page-{i}')
        page = self.client.get('/api/communications/history/')
        self.assertEqual((page.data['count'], len(page.data['results'])), (22, 20))
        self.assertIsNotNone(page.data['next'])

    def test_zero_audience_plain_text_and_query_bounds(self):
        ParentStudentLink.objects.all().delete()
        self.assertEqual(self.send().status_code, 400)
        self.assertEqual(Communication.objects.count(), 0)
        ParentStudentLink.objects.create(school=self.school, parent=self.parent, student=self.profile)
        payload = {**self.payload, 'body': '<script>alert(1)</script>'}
        self.assertEqual(self.send(payload).status_code, 201)
        self.client.force_authenticate(self.parent)
        with CaptureQueriesContext(connection) as inbox_queries:
            inbox = self.client.get('/api/communications/inbox/')
        self.assertEqual(inbox.data['results'][0]['body'], payload['body'])
        self.assertLessEqual(len(inbox_queries), 8)
        self.client.force_authenticate(self.admin)
        with CaptureQueriesContext(connection) as history_queries:
            self.client.get('/api/communications/history/')
        self.assertLessEqual(len(history_queries), 8)

    def test_hundred_linked_parents_do_not_add_one_query_per_recipient(self):
        parents = CustomUser.objects.bulk_create([
            CustomUser(email=f'parent-{i}@notice.test', first_name='Parent', last_name=str(i),
                       school=self.school, role='parent', is_active=True) for i in range(100)
        ])
        ParentStudentLink.objects.bulk_create([
            ParentStudentLink(school=self.school, parent=parent, student=self.profile) for parent in parents
        ])
        payload = {'audience': 'all_parents', 'title': 'Holiday', 'body': 'School closes early.'}
        with CaptureQueriesContext(connection) as preview_queries:
            preview = self.client.post('/api/communications/preview/', payload, format='json')
        self.assertEqual(preview.data['recipient_count'], 101)
        with CaptureQueriesContext(connection) as send_queries:
            sent = self.send(payload)
        self.assertEqual(sent.status_code, 201, sent.data)
        self.assertEqual(CommunicationRecipient.objects.count(), 101)
        self.assertLessEqual(len(preview_queries), 12)
        self.assertLessEqual(len(send_queries), 18)
