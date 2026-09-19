"""Isolated test database and local service substitutes; never uses deployment data."""
from .local import *  # noqa: F401,F403
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Local/test encryption key only; production must supply its own secret.
PLATFORM_MFA_KEY = "aW50ZWdyYXRpb24tbWZhLWtleS0zMi1ieXRlcy1sb2M="
