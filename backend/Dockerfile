FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.production

# System deps: WeasyPrint PDF + psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 libffi-dev libcairo2 libxml2 libxslt1.1 \
    libpq-dev postgresql-client gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps before copying source (layer cache)
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Collect static files at build time using valid dummy values that satisfy
# the production settings checks without disabling runtime security rules.
RUN SECRET_KEY=dummy-build-secret \
    ALLOWED_HOSTS=localhost,127.0.0.1 \
    DATABASE_URL=sqlite:///dev-dummy.db \
    REDIS_URL=redis://localhost:6379/0 \
    FRONTEND_URL=https://example.com \
    CORS_ALLOWED_ORIGINS=https://example.com \
    PAYSTACK_MODE=test \
    PAYSTACK_SECRET_KEY=sk_test_dummy_key \
    PLATFORM_MFA_KEY=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA= \
    python manage.py collectstatic --noinput

# Non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl --fail http://localhost:8000/health/ || exit 1

ENTRYPOINT ["bash", "entrypoint.sh"]

