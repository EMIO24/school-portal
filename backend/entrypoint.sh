#!/usr/bin/env bash
set -e

# Only run migrations for the web service (not for celery/celery-beat)
if [ "$RUN_MIGRATIONS" = "true" ]; then
    python manage.py deployment_check ${DEPLOYMENT_CHECK_ARGS:-}
    python manage.py check --deploy --fail-level WARNING
    echo "==> Running database migrations..."
    python manage.py migrate --noinput

    # Create superadmin from env vars (idempotent — skips if email already exists)
    if [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
        python manage.py shell <<'PYTHON'
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email = os.environ['DJANGO_SUPERUSER_EMAIL']
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=os.environ['DJANGO_SUPERUSER_PASSWORD'])
    print('Platform owner created.')
PYTHON
    fi

    echo "==> Starting Gunicorn..."
    exec gunicorn config.wsgi:application \
        --bind "0.0.0.0:${PORT:-8000}" \
        --workers "${GUNICORN_WORKERS:-2}" \
        --worker-class gthread \
        --threads 4 \
        --timeout 120 \
        --access-logfile - \
        --error-logfile -
else
    # For celery/celery-beat: just run the command passed
    exec "$@"
fi
