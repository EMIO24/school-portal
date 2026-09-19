from urllib.parse import quote, urlsplit
import requests
from django.conf import settings

PAYSTACK_BASE = 'https://api.paystack.co'

class PaystackService:
    def __init__(self):
        self.secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
        self.mode = getattr(settings, 'PAYSTACK_MODE', 'test')
        if self.mode not in ('test', 'live') or not self.secret_key.startswith('sk_' + self.mode + '_'):
            raise ValueError('Paystack is not configured for this environment. Contact the platform owner.')
        self.headers = {'Authorization': 'Bearer ' + self.secret_key, 'Content-Type': 'application/json'}

    def _data(self, response):
        try:
            data = response.json()
        except ValueError:
            raise ValueError('Paystack returned an invalid response. Please try again later.')
        if response.status_code >= 400 or not isinstance(data, dict) or data.get('status') is not True or not isinstance(data.get('data'), dict):
            raise ValueError('Paystack could not process this request. Please check configuration or try again later.')
        return data['data']

    def initialize(self, email, amount_kobo, reference, callback_url, subaccount=None):
        payload = {'email': email, 'amount': int(amount_kobo), 'currency': 'NGN', 'reference': reference, 'callback_url': callback_url}
        if subaccount:
            # No platform commission on school fees; Paystack processing fees are
            # deducted from the school's settlement, not added to student fees.
            payload.update(subaccount=subaccount, transaction_charge=0, bearer='subaccount')
        data = self._data(requests.post(PAYSTACK_BASE + '/transaction/initialize', json=payload, headers=self.headers, timeout=15))
        url = data.get('authorization_url', '')
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.hostname != 'checkout.paystack.com' or data.get('reference') != reference:
            raise ValueError('Paystack returned unexpected checkout details.')
        return url, reference

    def verify(self, reference):
        return self._data(requests.get(PAYSTACK_BASE + '/transaction/verify/' + quote(reference, safe=''), headers=self.headers, timeout=15))

    def subaccount(self, code):
        return self._data(requests.get(PAYSTACK_BASE + '/subaccount/' + quote(code, safe=''), headers=self.headers, timeout=15))
