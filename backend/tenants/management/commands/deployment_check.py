"""Fail closed on missing production prerequisites, without printing secret values."""
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from urllib.parse import urlparse
from cryptography.fernet import Fernet
import ssl

class Command(BaseCommand):
    help = 'Validate production configuration; never prints secret values.'
    def add_arguments(self, parser):
        parser.add_argument('--allow-test-payments', action='store_true', help='Staging only.')
    def handle(self, *args, **options):
        errors = []
        if settings.DEBUG: errors.append('DEBUG must be false.')
        if len(settings.SECRET_KEY) < 50 or 'django-insecure' in settings.SECRET_KEY: errors.append('Set a strong unique SECRET_KEY of at least 50 characters.')
        if not settings.ALLOWED_HOSTS or '*' in settings.ALLOWED_HOSTS: errors.append('Set explicit ALLOWED_HOSTS.')
        origin = urlparse(settings.FRONTEND_URL)
        if origin.scheme != 'https' or not origin.hostname: errors.append('FRONTEND_URL must use HTTPS.')
        try:
            Fernet(settings.PLATFORM_MFA_KEY.encode())
            if settings.PLATFORM_MFA_KEY == 'aW50ZWdyYXRpb24tbWZhLWtleS0zMi1ieXRlcy1sb2M=': raise ValueError()
        except Exception: errors.append('Set a unique valid PLATFORM_MFA_KEY and back it up separately.')
        if not settings.SECURE_SSL_REDIRECT: errors.append('Enable SECURE_SSL_REDIRECT behind the trusted proxy.')
        if not settings.DATABASES['default']['ENGINE'].endswith('postgresql'): errors.append('Production requires PostgreSQL.')
        redis_url = urlparse(settings.REDIS_URL)
        is_tls_redis = redis_url.scheme == 'rediss'
        is_railway_private = (
            redis_url.scheme == 'redis'
            and bool(redis_url.hostname)
            and redis_url.hostname.endswith('.railway.internal')
        )
        if not (is_tls_redis or is_railway_private):
            errors.append('REDIS_URL must use TLS unless using Railway private networking.')
        mode = settings.PAYSTACK_MODE
        if mode != 'live' and not options['allow_test_payments']: errors.append('Set PAYSTACK_MODE=live for production; test mode is staging-only.')
        if not settings.PAYSTACK_SECRET_KEY.startswith('sk_'+mode+'_'): errors.append('Set the Paystack secret for the selected mode.')
        for name in ('TERMII_API_KEY','BREVO_API_KEY'):
            if not getattr(settings,name,''): errors.append('Set '+name+' before enabling delivery.')
        if errors: raise CommandError('Deployment blocked:\n- '+'\n- '.join(errors))
        self.stdout.write(self.style.SUCCESS('Configuration checks passed. Complete provider, restore and browser smoke checks before launch.'))
