from django.db import transaction

from .models import ClassArm, ClassLevel
from .placement_lock import lock_school, campus_is_active


class ClassStructureError(ValueError):
    pass


@transaction.atomic
def ensure_default_arm(*, school, class_level, campus=None):
    """Return the implicit placement container used by a school without named arms."""
    school = lock_school(school)
    if school.uses_class_arms:
        raise ClassStructureError("This school uses named class arms.")
    if campus and not campus_is_active(school, campus.pk):
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


@transaction.atomic
def resolve_class_for_admission(*, school, class_level, class_arm=None, campus=None):
    school = lock_school(school)
    if campus and not campus_is_active(school, campus.pk):
        raise ClassStructureError("Choose an active campus in this school.")
    if school.uses_class_arms:
        if not class_arm:
            raise ClassStructureError("Choose a class arm for this school.")
        class_arm = ClassArm.objects.filter(pk=class_arm.pk, school=school).first()
        if not class_arm or class_arm.class_level_id != class_level.pk:
            raise ClassStructureError("Class arm must belong to the selected class level.")
        if not campus_is_active(school, class_arm.campus_id):
            raise ClassStructureError("Choose a class in an active campus in this school.")
        if campus and class_arm.campus_id not in (None, campus.pk):
            raise ClassStructureError("Class arm does not belong to the selected campus.")
        return class_arm
    return ensure_default_arm(school=school, class_level=class_level, campus=campus)
