"""
config/settings/development.py

Development-specific settings.
Imports everything from base.py and overrides what's needed.
"""

from .base import *

# ── Security ───────────────────────────────────────────────────────────────

SECRET_KEY = "django-insecure-dev-key-change-before-production-use"

DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    ".localhost",      # covers *.localhost subdomains for tenant testing
]

# ── Database ───────────────────────────────────────────────────────────────
# Update NAME, USER, PASSWORD to match your local PostgreSQL setup

DATABASES = {
    "default": {
        "ENGINE":   "django.db.backends.postgresql",
        "NAME":     "school_portal",
        "USER":     "postgres",
        "PASSWORD": "postgres",      # ← change to your postgres password
        "HOST":     "localhost",
        "PORT":     "5432",
    }
}

# ── CORS (allow all origins in development) ────────────────────────────────

CORS_ALLOW_ALL_ORIGINS = True

# ── Email (print to console in development) ───────────────────────────────

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ── Django debug toolbar (optional) ───────────────────────────────────────
# Uncomment if you install django-debug-toolbar
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
# INTERNAL_IPS = ["127.0.0.1"]