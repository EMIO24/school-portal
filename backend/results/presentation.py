"""Shared, bounded presentation choices for official and preview report cards."""
from tenants.document_branding import school_branding_context
from .models import ReportConfiguration, PublishedReportStyle


DEFAULTS = {
    'layout': 'classic', 'title': 'Student Academic Report',
    'show_comments': True, 'show_attendance': True, 'show_position': True,
    'show_skills': True, 'show_next_term': True, 'watermark': 'none',
}
FIELDS = tuple(DEFAULTS)


def current_configuration(school):
    config = ReportConfiguration.objects.filter(school=school).first()
    return {name: getattr(config, name) if config else default
            for name, default in DEFAULTS.items()}


def presentation(school, term, *, preview=False):
    """Existing published terms without a snapshot retain the original default look."""
    if not preview:
        snapshot = PublishedReportStyle.objects.filter(school=school, term=term).first()
        if snapshot:
            return {**snapshot.branding, **snapshot.configuration}
        from gradebook.models import ScoreEntry
        if ScoreEntry.objects.filter(school=school, term=term, is_published=True).exists():
            return {**school_branding_context(school), **DEFAULTS}
    return {**school_branding_context(school), **current_configuration(school)}


def capture_presentation(school, term):
    from gradebook.models import ScoreEntry
    existing_publication = ScoreEntry.objects.filter(
        school=school, term=term, is_published=True).exists()
    return PublishedReportStyle.objects.get_or_create(
        school=school, term=term,
        defaults={'configuration': DEFAULTS.copy() if existing_publication else current_configuration(school),
                  'branding': school_branding_context(school)},
    )[0]


def has_complete_published_result(school, student, term):
    """A partially reopened result is unavailable as an official result."""
    from django.db.models import Count, Q
    from gradebook.models import ScoreEntry
    counts = ScoreEntry.objects.filter(school=school, student=student, term=term).aggregate(
        total=Count('id'), published=Count('id', filter=Q(is_published=True)),
    )
    return counts['total'] > 0 and counts['total'] == counts['published']
