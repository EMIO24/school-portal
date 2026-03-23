"""
enrollment/utils.py

Utilities for generating unique, human-readable IDs.

Admission number format:  SLUG-YYYY-XXXX   e.g.  GHS-2024-0042
Staff ID format:          SLUG-STAFF-XXXX  e.g.  GHS-STAFF-0007

Both use SELECT FOR UPDATE on the latest record to avoid race conditions
when two enrollments are submitted simultaneously (common during bulk import).
"""

from datetime import date
from django.db import transaction


@transaction.atomic
def generate_admission_number(school) -> str:
    """
    Generate the next sequential admission number for a school in the
    current calendar year.

    Format: {SLUG}-{YEAR}-{SEQUENCE:04d}
    Example: GHS-2024-0042

    Uses SELECT FOR UPDATE to lock the latest record and prevent
    duplicate numbers under concurrent requests.
    """
    from .models import StudentProfile

    year = date.today().year
    prefix = f"{school.slug.upper()}-{year}-"

    # Lock and fetch the highest existing number for this school + year
    latest = (
        StudentProfile.objects
        .select_for_update()
        .filter(
            school=school,
            admission_number__startswith=prefix,
        )
        .order_by("-admission_number")
        .first()
    )

    if latest:
        try:
            last_seq = int(latest.admission_number.split("-")[-1])
        except (ValueError, IndexError):
            last_seq = 0
        next_seq = last_seq + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:04d}"


@transaction.atomic
def generate_staff_id(school) -> str:
    """
    Generate the next sequential staff ID for a school.

    Format: {SLUG}-STAFF-{SEQUENCE:04d}
    Example: GHS-STAFF-0007
    """
    from .models import StaffProfile

    prefix = f"{school.slug.upper()}-STAFF-"

    latest = (
        StaffProfile.objects
        .select_for_update()
        .filter(
            school=school,
            staff_id__startswith=prefix,
        )
        .order_by("-staff_id")
        .first()
    )

    if latest:
        try:
            last_seq = int(latest.staff_id.split("-")[-1])
        except (ValueError, IndexError):
            last_seq = 0
        next_seq = last_seq + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:04d}"