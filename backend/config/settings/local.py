"""
config/settings/local.py

Settings for local development and CI environments.
Inherits from development.py; overrides DB with DATABASE_URL when present
(used in GitHub Actions test job).
"""

import os

import dj_database_url

from .development import *  # noqa: F401, F403

DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.config(
            env="DATABASE_URL",
            conn_max_age=0,
            ssl_require=False,
        )
    }
