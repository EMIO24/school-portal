import uuid
import requests
from django.conf import settings

PAYSTACK_BASE = "https://api.paystack.co"


class PaystackService:

    def __init__(self):
        self.secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        self.headers    = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type":  "application/json",
        }

    def initialize(self, email, amount_kobo, reference, callback_url):
        payload = {
            "email":        email,
            "amount":       int(amount_kobo),
            "reference":    reference,
            "callback_url": callback_url,
        }
        resp = requests.post(
            f"{PAYSTACK_BASE}/transaction/initialize",
            json=payload,
            headers=self.headers,
            timeout=15,
        )
        data = resp.json()
        if not data.get('status'):
            raise ValueError(data.get('message', 'Paystack initialization failed'))
        return data['data']['authorization_url'], data['data']['reference']

    def verify(self, reference):
        resp = requests.get(
            f"{PAYSTACK_BASE}/transaction/verify/{reference}",
            headers=self.headers,
            timeout=15,
        )
        data = resp.json()
        if not data.get('status'):
            raise ValueError(data.get('message', 'Paystack verification failed'))
        return data['data']
