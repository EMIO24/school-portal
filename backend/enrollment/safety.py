from rest_framework.exceptions import ValidationError


class RetainAcademicHistoryMixin:
    """Only unused academic configuration can be removed through the portal."""

    def perform_destroy(self, instance):
        for relation in instance._meta.related_objects:
            if relation.one_to_many or relation.many_to_many:
                manager = getattr(instance, relation.get_accessor_name(), None)
                if manager is not None and manager.exists():
                    raise ValidationError('This record is in use. Keep it to preserve school history.')
        instance.delete()
