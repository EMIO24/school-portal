"""
config/settings/base.py

Complete base settings for the school portal.
"""

from datetime import timedelta
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Security ───────────────────────────────────────────────────────────────
# Override SECRET_KEY in development.py and production.py

SECRET_KEY = "django-insecure-change-this-in-production"

DEBUG = False  # overridden per environment

ALLOWED_HOSTS = []

# ── Applications ───────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",

    # Local apps — ORDER MATTERS
    "tenants",
    "accounts",
    "academics",
    "enrollment",
    "results",

    # Future apps
    "analytics",
    "attendance",
    "cbt",
    "fees",
    "gradebook",
    "notifications",
    "promotion",
    "timetable",
]

# ── Middleware ─────────────────────────────────────────────────────────────

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "tenants.middleware.TenantMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ── URL & WSGI ─────────────────────────────────────────────────────────────

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# ── Templates ──────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
TEMPLATES[0]['DIRS'] += [BASE_DIR / 'results' / 'pdf_templates']
# ── Database ───────────────────────────────────────────────────────────────
# Overridden in development.py and production.py

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "school_portal",
        "USER": "postgres",
        "PASSWORD": "",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# ── Auth ───────────────────────────────────────────────────────────────────

AUTH_USER_MODEL = "accounts.CustomUser"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internationalisation ───────────────────────────────────────────────────

LANGUAGE_CODE = "en-us"
TIME_ZONE     = "Africa/Lagos"
USE_I18N      = True
USE_TZ        = True

# ── Static & Media ─────────────────────────────────────────────────────────

STATIC_URL  = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Default primary key ────────────────────────────────────────────────────

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── REST Framework ─────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
}

# ── Simple JWT ─────────────────────────────────────────────────────────────

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":    timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME":   timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":    True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM":                "HS256",
    "SIGNING_KEY":              None,  # falls back to SECRET_KEY
    "AUTH_HEADER_TYPES":        ("Bearer",),
    "AUTH_HEADER_NAME":         "HTTP_AUTHORIZATION",
    "USER_ID_FIELD":            "id",
    "USER_ID_CLAIM":            "user_id",
    "AUTH_TOKEN_CLASSES":       ("rest_framework_simplejwt.tokens.AccessToken",),
}

# ── CORS ───────────────────────────────────────────────────────────────────

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[\w-]+\.myplatform\.com$",
    r"^http://[\w-]+\.localhost(:\d+)?$",
    r"^http://localhost(:\d+)?$",
]

CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-csrftoken",
    "x-requested-with",
]

# ── Cloudinary ─────────────────────────────────────────────────────────────
# Set real values in development.py / production.py via env vars

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": "",
    "API_KEY":    "",
    "API_SECRET": "",
}

# ── Email (override in production.py) ─────────────────────────────────────

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ── Celery (override in production.py) ────────────────────────────────────

CELERY_BROKER_URL        = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND    = "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT    = ["json"]
CELERY_TASK_SERIALIZER   = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE          = "Africa/Lagos"