from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework import serializers
from accounts.school_access import require_assignment
from academics.models import Term
from enrollment.models import ClassArm, Subject, StudentProfile
from tenants.models import School, PlatformEvent
from .models import ScoreEntry
from .scoring import checked_scores


def lock_school(school):
    return School.objects.select_for_update().get(pk=school.pk)


def require_unpublished(school, student, term):
    if ScoreEntry.objects.filter(school=school, student=student, term=term, is_published=True).exists():
        raise ValidationError('Published results are locked. Reopen all affected scores before correcting the result.')

@transaction.atomic
def transition(request, action):
    school = lock_school(request.tenant)
    if action != 'submit' and request.user.role != 'school_admin':
        raise PermissionDenied('Only school administrators can approve or publish results.')
    params = {**request.query_params.dict(), **request.data}
    ids = {key:serializers.IntegerField(min_value=1).run_validation(params.get(key)) for key in ('class_arm','subject','term')}
    arm = get_object_or_404(ClassArm,pk=ids['class_arm'],school=school)
    get_object_or_404(Subject,pk=ids['subject'],school=school)
    term = get_object_or_404(Term,pk=ids['term'],session__school=school)
    require_assignment(request,arm.pk,term.pk,ids['subject'])
    rows = list(ScoreEntry.objects.select_for_update().filter(school=school,**{k+'_id':v for k,v in ids.items()}).select_related('policy'))
    expected = set(StudentProfile.objects.filter(school=school,current_class=arm,status='active').values_list('user_id',flat=True))
    if not rows or not expected.issubset({row.student_id for row in rows}):
        raise ValidationError('Every active student needs a score row before this result can proceed.')
    required = {'submit':'draft','approve':'submitted','publish':'approved'}[action]
    for row in rows:
        if row.is_published or row.review_state != required:
            raise ValidationError(f'All selected rows must be {required} before {action}.')
        if row.policy_id:
            checked_scores(row.policy,row.component_scores,complete=True)
        elif not row.grade:
            raise ValidationError('Review the legacy score row before submission.')
    qs = ScoreEntry.objects.filter(pk__in=[row.pk for row in rows])
    if action == 'publish': qs.update(is_published=True)
    else: qs.update(review_state={'submit':'submitted','approve':'approved'}[action])
    PlatformEvent.objects.create(actor=request.user,actor_email=request.user.email,action='school.results_'+action,
        target=str(term.pk),details={'school_id':school.pk,**ids,'entries':[row.pk for row in rows]})
    return {{'submit':'submitted','approve':'approved','publish':'published'}[action]:len(rows)}
