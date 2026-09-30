from django.contrib.auth.hashers import make_password
from django.test import TestCase
from rest_framework.test import APIClient

from enrollment import test_operations as operations
from .models import ScratchCard


class PublicResultCardAvailabilityTests(TestCase):
    user = classmethod(operations.BasicOperationsTests.user.__func__)
    setUpTestData = classmethod(operations.BasicOperationsTests.setUpTestData.__func__)

    def test_unpublished_result_does_not_consume_card(self):
        from django.core.cache import cache
        cache.clear()
        card = ScratchCard.objects.create(school=self.school, term=self.term, serial_number='CURRICULUM-CARD-1',
            pin_hash=make_password('12345678'), batch_name='Test')
        client = APIClient()
        payload = {'admission_number': self.profile.admission_number, 'serial_number': card.serial_number, 'pin': '12345678'}
        response = client.post('/api/results/check/', payload, format='json')
        self.assertEqual(response.status_code, 403)
        card.refresh_from_db()
        self.assertFalse(card.is_used)
        self.score.is_published = True
        self.score.save()
        response = client.post('/api/results/check/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        card.refresh_from_db()
        self.assertTrue(card.is_used)
        self.assertEqual(client.post('/api/results/check/', payload, format='json').status_code, 403)
