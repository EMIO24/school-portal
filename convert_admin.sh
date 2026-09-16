#!/bin/bash
# Convert admin to school_admin
cd /mnt/c/Users/user/school-portal

docker compose exec -T web python3 << 'PYSCRIPT'
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.docker")
django.setup()

from django.contrib.auth import get_user_model
from tenants.models import School

User = get_user_model()

# Get school and user
school = School.objects.get(subdomain="testschool")
user = User.objects.get(email="admin@testschool.ng")

print(f"Before: {user.email} - role={user.role}, school={user.school}, is_superuser={user.is_superuser}")

# Update user
user.school = school
user.role = "school_admin"
user.is_staff = True
user.is_superuser = False
user.save()

print(f"After:  {user.email} - role={user.role}, school={user.school}, is_superuser={user.is_superuser}")
PYSCRIPT
