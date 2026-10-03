from django.db import transaction

from .models import ClassArm, ClassLevel


class ClassStructureError(ValueError):
    pass


@transaction.atomic
def ensure_default_arm(*, school, class_level, campus=None):
    """Return the implicit placement container used by a school without named arms."""
    if school.uses_class_arms:
        raise ClassStructureError("This school uses named class arms.")
    if campus and (campus.school_id != school.pk or not campus.is_active):
        raise ClassStructureError("Choose an active campus in this school.")
    level = ClassLevel.objects.select_for_update().filter(pk=class_level.pk, school=school).first()
    if not level:
        raise ClassStructureError("Class level must belong to this school.")
    campus_id = campus.pk if campus else None
    arm = ClassArm.objects.filter(
        school=school, class_level=level, is_default=True, campus_id=campus_id
    ).first()
    if arm:
        return arm
    return ClassArm.objects.create(
        school=school,
        class_level=level,
        name="",
        is_default=True,
        campus=campus,
    )


def resolve_class_for_admission(*, school, class_level, class_arm=None, campus=None):
    if campus and (campus.school_id != school.pk or not campus.is_active):
        raise ClassStructureError("Choose an active campus in this school.")
    if school.uses_class_arms:
        if not class_arm:
            raise ClassStructureError("Choose a class arm for this school.")
        if class_arm.school_id != school.pk or class_arm.class_level_id != class_level.pk:
            raise ClassStructureError("Class arm must belong to the selected class level.")
        if class_arm.campus_id and (class_arm.campus.school_id != school.pk or not class_arm.campus.is_active):
            raise ClassStructureError("Choose a class in an active campus in this school.")
        if campus and class_arm.campus_id not in (None, campus.pk):
            raise ClassStructureError("Class arm does not belong to the selected campus.")
        return class_arm
    return ensure_default_arm(school=school, class_level=class_level, campus=campus)
