#!/usr/bin/env bash
# setup_school.sh - Create the idempotent local fixture used by API tests.
set -euo pipefail

cd "$(dirname "$0")"

if docker compose version >/dev/null 2>&1; then
  compose=(docker compose)
else
  compose=(docker-compose)
fi

"${compose[@]}" exec -T web python manage.py shell -c "
from django.contrib.auth import get_user_model
from tenants.models import School

school, _ = School.objects.get_or_create(
    subdomain='testschool',
    defaults={'name': 'Test School', 'slug': 'testschool', 'is_active': True},
)
school.name = 'Test School'
school.slug = 'testschool'
school.is_active = True
school.save()

User = get_user_model()
admin, created = User.objects.get_or_create(
    email='admin@testschool.ng',
    defaults={
        'first_name': 'Test', 'last_name': 'Administrator',
        'school': school, 'role': 'school_admin',
        'is_staff': True, 'is_active': True, 'must_change_password': False,
    },
)
admin.first_name = 'Test'
admin.last_name = 'Administrator'
admin.school = school
admin.role = 'school_admin'
admin.is_staff = True
admin.is_active = True
admin.must_change_password = False
admin.set_password('AdminStr0ng#1')
admin.save()

print(f'Prepared {school.subdomain} and {admin.email}')
"
