from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .history import assignment_has_history
from .models import SubjectAssignment
from tenants.models import School


@receiver(pre_delete, sender=SubjectAssignment)
def protect_historical_subject_assignment(sender, instance, using, **kwargs):
    origin = kwargs.get('origin')
    # A deliberate top-level tenant teardown (used by the isolated demo reset)
    # owns the destruction of all tenant history. Ordinary assignment/staff
    # deletion must not cascade through historical teaching responsibility.
    if isinstance(origin, School) or getattr(origin, 'model', None) is School:
        return
    if assignment_has_history(instance):
        raise ValidationError(
            'This teaching assignment has academic history and must be retained.'
        )
