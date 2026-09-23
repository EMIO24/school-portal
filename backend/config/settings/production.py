"""
config/settings/production.py

Production settings for Railway deployment.
All secrets come from environment variables â€” never hard-coded.

Deploy checklist:
  1. Set SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, PAYSTACK_SECRET_KEY,
     TERMII_API_KEY, CLOUDINARY_*, BREVO_API_KEY in Railway Variables tab.
  2. DATABASE_URL is auto-injected when you add the Railway PostgreSQL add-on.
  3. REDIS_URL must be set to the Railway Redis URL (redis://...railway.internal or rediss://... for TLS).
  4. FRONTEND_URL should be your Vercel frontend URL for CORS.
"""

import os
import ssl
import dj_database_url

from .base import *  # noqa: F401, F403

# â”€â”€ Security â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = False

ALLOWED_HOSTS = [host.strip() for host in os.environ.get('ALLOWED_HOSTS', '').split(',') if host.strip()]
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise RuntimeError('Production requires explicit ALLOWED_HOSTS.')

# â”€â”€ Database â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        conn_max_age=600,
        ssl_require=True,
    )
}

# â”€â”€ Cache / Celery (Railway Redis via private networking or TLS) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

REDIS_URL = os.environ["REDIS_URL"]
_tls_redis = REDIS_URL.startswith("rediss://")

CACHES = {
    "default": {
        "BACKEND":  "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            **({"CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": ssl.CERT_REQUIRED}} if _tls_redis else {}),
        },
    }
}

CELERY_BROKER_URL     = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

if _tls_redis:
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}

# â”€â”€ Static files (WhiteNoise) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
] + MIDDLEWARE[1:]  # noqa: F405

_cloudinary_required = ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
if not all(os.environ.get(name) for name in _cloudinary_required):
    raise RuntimeError("Production image storage requires CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET.")
STORAGES = {
    'default': {'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405

# â”€â”€ CORS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

FRONTEND_URL = os.environ["FRONTEND_URL"].rstrip('/')
if not FRONTEND_URL.startswith('https://'):
    raise RuntimeError('Production FRONTEND_URL must use HTTPS.')

CORS_ALLOWED_ORIGIN_REGEXES = []
CORS_ALLOWED_ORIGINS = [origin.strip().rstrip('/') for origin in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',') if origin.strip()]

if FRONTEND_URL:
    CORS_ALLOWED_ORIGINS += [FRONTEND_URL.rstrip("/")]

CSRF_TRUSTED_ORIGINS = [FRONTEND_URL]

CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-school-slug",
    "idempotency-key",
]

CORS_EXPOSE_HEADERS = ["x-request-id"]

# Railway captures stdout/stderr, so keep production diagnostics structured and
# dependency-free. Application logs deliberately omit request bodies and headers.
_log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
if _log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
    _log_level = "INFO"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "railway": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "railway"},
    },
    "root": {"handlers": ["console"], "level": _log_level},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

# â”€â”€ HTTPS / Cookies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r'^health/$']
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER        = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE          = True
CSRF_COOKIE_SECURE             = True
SECURE_HSTS_SECONDS            = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# â”€â”€ Email (Brevo REST API â€” bypasses Django's SMTP backend) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Django's email system is NOT used in production. The notifications service
# calls Brevo's REST API directly via requests. Set EMAIL_BACKEND to dummy
# Generic Django email is unused; application delivery is logged by provider services.

EMAIL_BACKEND    = "config.email_backend.DisabledEmailBackend"
BREVO_API_KEY    = os.environ.get("BREVO_API_KEY", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@schoolportal.ng")

# â”€â”€ Third-party keys â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

PAYSTACK_MODE = os.environ.get("PAYSTACK_MODE", "live")
if PAYSTACK_MODE not in ('test', 'live'):
    raise RuntimeError('PAYSTACK_MODE must be test or live.')
PAYSTACK_SECRET_KEY = os.environ["PAYSTACK_SECRET_KEY"]
if not PAYSTACK_SECRET_KEY.startswith('sk_' + PAYSTACK_MODE + '_'):
    raise RuntimeError('PAYSTACK_SECRET_KEY does not match PAYSTACK_MODE.')
TERMII_API_KEY      = os.environ.get("TERMII_API_KEY", "")

PLATFORM_MFA_KEY = os.environ["PLATFORM_MFA_KEY"]

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    "API_KEY":    os.environ.get("CLOUDINARY_API_KEY", ""),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", ""),
}

CORS_ALLOW_CREDENTIALS = False


