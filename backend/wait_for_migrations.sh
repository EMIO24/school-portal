#!/bin/bash
# Wait for Django migrations to complete
# This script checks if the django_migrations table exists

echo "Waiting for database migrations..."
max_attempts=60
attempt=0

while [ $attempt -lt $max_attempts ]; do
    python manage.py migrate --check --no-input 2>/dev/null && {
        echo "✓ Database migrations complete"
        exit 0
    }
    
    attempt=$((attempt + 1))
    echo "Checking migrations... ($attempt/$max_attempts)"
    sleep 2
done

echo "✗ Migrations did not complete within timeout"
exit 1
