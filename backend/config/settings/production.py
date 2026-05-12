"""
config/settings/production.py

Production settings for Railway deployment.
All secrets come from environment variables — never hard-coded.

Deploy checklist:
  1. Set SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, PAYSTACK_SECRET_KEY,
     TERMII_API_KEY, CLOUDINARY_*, BREVO_API_KEY in Railway Variables tab.
  2. DATABASE_URL is auto-injected when you add the Railway PostgreSQL add-on.
  3. REDIS_URL must be set to your Upstash Redis URL (rediss://... for TLS).
  4. FRONTEND_URL should be your Cloudflare Pages URL for CORS.
"""

import os
import dj_database_url

from .base import *  # noqa: F401, F403

# ── Security ───────────────────────────────────────────────────────────────

SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = False

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",") + [
    ".up.railway.app",
]

# ── Database ───────────────────────────────────────────────────────────────

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        conn_max_age=600,
        ssl_require=True,
    )
}

# ── Cache / Celery (Upstash Redis with TLS) ────────────────────────────────

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_upstash   = REDIS_URL.startswith("rediss://")

CACHES = {
    "default": {
        "BACKEND":  "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            **({"CONNECTION_POOL_KWARGS": {"ssl_cert_reqs": None}} if _upstash else {}),
        },
    }
}

CELERY_BROKER_URL     = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL

if _upstash:
    BROKER_USE_SSL       = {"ssl_cert_reqs": None}
    REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": None}

# ── Static files (WhiteNoise) ──────────────────────────────────────────────

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
] + MIDDLEWARE[1:]  # noqa: F405

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405

# ── CORS ───────────────────────────────────────────────────────────────────

FRONTEND_URL = os.environ.get("FRONTEND_URL", "")

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[\w-]+\.pages\.dev$",       # Cloudflare Pages preview + production
    r"^https://[\w-]+\.up\.railway\.app$", # Railway services
]

if FRONTEND_URL:
    CORS_ALLOWED_ORIGINS = [FRONTEND_URL.rstrip("/")]

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
]

# ── HTTPS / Cookies ────────────────────────────────────────────────────────

SECURE_PROXY_SSL_HEADER        = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE          = True
CSRF_COOKIE_SECURE             = True
SECURE_HSTS_SECONDS            = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# ── Email (Brevo REST API — bypasses Django's SMTP backend) ───────────────
# Django's email system is NOT used in production. The notifications service
# calls Brevo's REST API directly via requests. Set EMAIL_BACKEND to dummy
# so any accidental send_mail() calls fail loudly rather than silently queue.

EMAIL_BACKEND    = "django.core.mail.backends.dummy.EmailBackend"
BREVO_API_KEY    = os.environ.get("BREVO_API_KEY", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@schoolportal.ng")

# ── Third-party keys ───────────────────────────────────────────────────────

PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")
TERMII_API_KEY      = os.environ.get("TERMII_API_KEY", "")

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
    "API_KEY":    os.environ.get("CLOUDINARY_API_KEY", ""),
    "API_SECRET": os.environ.get("CLOUDINARY_API_SECRET", ""),
}
