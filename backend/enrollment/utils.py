"""Reserve stable institutional IDs using a database-backed prefix counter.

Formats remain SLUG-YYYY-XXXX and SLUG-STAFF-XXXX (minimum four digits).
Reservations are durable even when a caller inserts the profile later. Gaps are
allowed; issued numbers and committed reservations must never be recycled.
"""

from datetime import date
import re

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, transaction
from django.db.models import DecimalField, Max
from django.db.models.functions import Cast, Substr


MAX_IDENTIFIER_SEQUENCE = 2**63 - 1


def _reserve_identifier(school, model, field_name, prefix):
    from .models import InstitutionalIdentifierSequence

    if not school.pk:
        raise ValidationError("Save the school before reserving an identifier.")
    using = school._state.db or DEFAULT_DB_ALIAS
    field_length = model._meta.get_field(field_name).max_length
    with transaction.atomic(using=using):
        # A unique namespace also serializes two simultaneous first allocations.
        # Case-normalized slug collisions intentionally share this global counter,
        # matching the existing global uniqueness of the issued identifier.
        counters = InstitutionalIdentifierSequence.objects.using(using)
        counter, _ = counters.get_or_create(namespace=prefix)
        counter = counters.select_for_update().get(pk=counter.pk)

        # Read only numeric suffixes of this exact prefix, across all schools.
        # This bootstraps legacy IDs and accounts for later historical imports
        # without rewriting them or trusting lexicographic ordering.
        issued = model.objects.using(using).filter(**{
            field_name + "__startswith": prefix,
            field_name + "__regex": rf"^{re.escape(prefix)}[0-9]+$",
        }).aggregate(highest=Max(Cast(
            Substr(field_name, len(prefix) + 1),
            output_field=DecimalField(max_digits=128, decimal_places=0),
        )))['highest']
        next_sequence = max(counter.last_value, int(issued or 0)) + 1
        identifier = f"{prefix}{next_sequence:04d}"
        if next_sequence > MAX_IDENTIFIER_SEQUENCE or len(identifier) > field_length:
            raise ValidationError("Institutional identifier capacity is exhausted.")
        counter.last_value = next_sequence
        counter.save(using=using, update_fields=["last_value"])
        return identifier


def generate_admission_number(school) -> str:
    from .models import StudentProfile

    prefix = f"{school.slug.upper()}-{date.today().year}-"
    return _reserve_identifier(school, StudentProfile, "admission_number", prefix)


def generate_staff_id(school) -> str:
    from .models import StaffProfile

    prefix = f"{school.slug.upper()}-STAFF-"
    return _reserve_identifier(school, StaffProfile, "staff_id", prefix)
