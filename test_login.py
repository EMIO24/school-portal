#!/usr/bin/env python
"""Quick test to verify school setup and login response"""

import os
import sys
import django
import json

def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.docker")
    django.setup()

    from django.contrib.auth import get_user_model
    from tenants.models import School
    from rest_framework_simplejwt.tokens import RefreshToken

    User = get_user_model()

    # Check schools
    print("=" * 60)
    print("SCHOOLS IN DATABASE:")
    print("=" * 60)
    schools = School.objects.all()
    print(f"Total: {schools.count()}")
    for s in schools:
        print(f"  - {s.name} (subdomain={s.subdomain}, is_active={s.is_active})")

    if not schools.exists():
        print("\nCreating testschool...")
        school = School.objects.create(
            name="Test School",
            slug="testschool", 
            subdomain="testschool",
            is_active=True
        )
        print(f"✓ Created: {school.name}")

    # Check admin user
    print("\n" + "=" * 60)
    print("ADMIN USER:")
    print("=" * 60)
    admin = User.objects.get(email='admin@testschool.ng')
    print(f"Email: {admin.email}")
    print(f"Role: {admin.role}")
    print(f"Active: {admin.is_active}")
    print(f"School: {admin.school}")

    # Generate tokens
    print("\n" + "=" * 60)
    print("GENERATED TOKENS:")
    print("=" * 60)
    refresh = RefreshToken.for_user(admin)
    refresh["role"] = admin.role
    refresh["school_id"] = admin.school_id
    refresh["full_name"] = admin.full_name
    refresh.access_token["role"] = admin.role
    refresh.access_token["school_id"] = admin.school_id
    refresh.access_token["full_name"] = admin.full_name

    response = {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "role": admin.role,
        "must_change_password": admin.must_change_password,
    }

    print(f"Access token: {str(refresh.access_token)[:50]}...")
    print(f"Refresh token: {str(refresh)[:50]}...")
    print(f"\nResponse structure:")
    print(json.dumps(response, indent=2, default=str)[:500])


if __name__ == '__main__':
    main()
