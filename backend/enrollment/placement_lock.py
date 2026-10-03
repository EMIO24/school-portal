"""Serialize operational placement with campus retirement and session cutover."""
from django.db import transaction
from tenants.models import Campus, School


def lock_school(school):
    return School.objects.select_for_update().get(pk=school.pk)


def campus_is_active(school, campus_id):
    return campus_id is None or Campus.objects.filter(
        pk=campus_id, school=school, is_active=True,
    ).exists()


class PlacementWriteMixin:
    # Lock before DRF resolves related objects or validates cached configuration.
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        request.tenant = lock_school(request.tenant)
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        request.tenant = lock_school(request.tenant)
        return super().update(request, *args, **kwargs)
