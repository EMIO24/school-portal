"""Controlled assessment-source writes into the existing term gradebook."""
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import ValidationError

from gradebook.models import ScoreEntry
from gradebook.scoring import checked_scores, policy_for


@transaction.atomic
def integrate_component(*, school, student, subject, term, class_arm, key, source, raw_score, raw_maximum, teacher=None):
    """Store one source per component; retries are safe, competing sources fail."""
    if not source or not key:
        raise ValidationError('Select an explicit assessment source and component.')
    raw_score, raw_maximum = Decimal(str(raw_score)), Decimal(str(raw_maximum))
    if raw_maximum <= 0 or raw_score < 0 or raw_score > raw_maximum:
        raise ValidationError('Raw score must be within the assessment maximum.')
    if student.school_id != school.pk or subject.school_id != school.pk or term.session.school_id != school.pk or class_arm.school_id != school.pk:
        raise ValidationError('Assessment scope must belong to this school.')
    policy = policy_for(school, term)
    if not policy:
        raise ValidationError('Configure term scoring before integrating this assessment.')
    component = next((c for c in policy.components if c['key'] == key), None)
    if not component:
        raise ValidationError('The selected component is not configured for this term.')
    maximum = Decimal(str(component['maximum']))
    normalized = (raw_score / raw_maximum * maximum).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    normalized = min(normalized, maximum)

    # Lock the student row before the gradebook insert, including the first concurrent write.
    get_user_model().objects.select_for_update().get(pk=student.pk)
    lookup = dict(school=school, student=student, subject=subject, term=term, session=term.session)
    entry = ScoreEntry.objects.select_for_update().filter(**lookup).first()
    if not entry:
        entry = ScoreEntry(**lookup, class_arm=class_arm, policy=policy, teacher=teacher)
        entry.component_scores = {c['key']: None for c in policy.components}
    elif entry.class_arm_id != class_arm.pk or (entry.policy_id and entry.policy_id != policy.pk):
        raise ValidationError('Existing gradebook entry has a different class or scoring policy.')

    existing_source = entry.component_sources.get(key)
    if existing_source and existing_source != source:
        raise ValidationError('Another assessment already supplies this component.')
    if existing_source == source:
        return entry, False, normalized
    if entry.is_published or entry.review_state != 'draft':
        raise ValidationError('Gradebook scores are locked; an administrator must reopen them first.')
    if entry.component_scores.get(key) not in (None, ''):
        raise ValidationError('This component already has a manually entered score.')
    scores = dict(entry.component_scores)
    scores[key] = str(normalized)
    entry.component_scores = checked_scores(policy, scores)
    entry.component_sources = {**entry.component_sources, key: source}
    entry.policy = policy
    entry.save()
    return entry, True, normalized
