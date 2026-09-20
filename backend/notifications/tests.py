from django.test import TestCase

from notifications.models import NotificationBatch, NotificationLog, NotificationOutbox
from tenants.models import School


class NotificationOutboxTests(TestCase):
    def test_log_reverse_relation_uses_outbox_name(self):
        school = School.objects.create(
            name='Test School',
            slug='test-school',
            subdomain='test-school',
        )
        batch = NotificationBatch.objects.create(
            school=school,
            key='batch-1',
            digest='abc123',
        )
        log = NotificationLog.objects.create(
            school=school,
            channel='email',
            recipient_email='hello@example.com',
            message_body='Hello from the outbox.',
        )
        outbox = NotificationOutbox.objects.create(
            batch=batch,
            log=log,
            subject='Welcome',
        )

        self.assertQuerySetEqual(
            NotificationLog.objects.filter(outbox=outbox),
            [log.pk],
            transform=lambda obj: obj.pk,
        )
