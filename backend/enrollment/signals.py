from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .history import assignment_has_history
from .models import SubjectAssignment


@receiver(pre_delete, sender=SubjectAssignment)
def protect_historical_subject_assignment(sender, instance, using, **kwargs):
    if assignment_has_history(instance):
        raise ValidationError(
            'This teaching assignment has academic history and must be retained.'
        )
