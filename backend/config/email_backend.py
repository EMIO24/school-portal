from django.core.mail.backends.base import BaseEmailBackend
from django.core.exceptions import ImproperlyConfigured

class DisabledEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise ImproperlyConfigured('Use the audited notification outbox for email delivery.')
