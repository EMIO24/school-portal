"""Persistent local browser-test sandbox. Select explicitly; never deploy this setting."""
import os
from .test import *  # noqa: F401,F403

INTEGRATION_DIR = BASE_DIR.parent / '.testing'
INTEGRATION_DIR.mkdir(exist_ok=True)
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(INTEGRATION_DIR / 'portal.sqlite3')}}
SECRET_KEY = 'local-integration-only-key-not-for-deployment-2026'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
MEDIA_ROOT = INTEGRATION_DIR / 'media'
PAYSTACK_MODE = 'test'
FRONTEND_URL = 'http://localhost:3001'
PAYSTACK_SECRET_KEY = ''
payment_config = INTEGRATION_DIR / 'paystack.json'
if payment_config.exists():
    import json
    payment_values = json.loads(payment_config.read_text(encoding='utf-8-sig'))
    candidate = payment_values.get('secret_key', '')
    if not candidate.startswith('sk_test_'):
        raise ValueError('The integration sandbox accepts only Paystack test keys.')
    PAYSTACK_SECRET_KEY = candidate
TERMII_API_KEY = ''
os.environ['BREVO_API_KEY'] = ''
CLOUDINARY_STORAGE = {'CLOUD_NAME': '', 'API_KEY': '', 'API_SECRET': ''}

# Provider calls fail locally, so browser testing cannot charge or message anyone.
# Django's in-process test client and incoming runserver requests are unaffected.
import requests

_original_provider_request = requests.sessions.Session.request

def _blocked_provider_request(self, method, url, **kwargs):
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if PAYSTACK_SECRET_KEY and parsed.scheme == 'https' and parsed.netloc == 'api.paystack.co' and kwargs.get('headers', {}).get('Authorization') == 'Bearer ' + PAYSTACK_SECRET_KEY:
        kwargs['allow_redirects'] = False
        return _original_provider_request(self, method, url, **kwargs)
    raise requests.ConnectionError('External HTTP is disabled in the integration sandbox.')

requests.sessions.Session.request = _blocked_provider_request

# Capture notification attempts locally for browser testing.
NOTIFICATIONS_CAPTURE_ONLY = True
