"""Freeze the best-known presentation for results published before Batch 15.

Earlier visual history is not recoverable; preserve the upgrade-time identity
and original default layout instead of applying future school settings.
"""
from django.db import migrations


def snapshot_existing(apps, schema_editor):
    Score = apps.get_model('gradebook', 'ScoreEntry')
    School = apps.get_model('tenants', 'School')
    Style = apps.get_model('results', 'PublishedReportStyle')
    db = schema_editor.connection.alias
    defaults = {'layout': 'classic', 'title': 'Student Academic Report',
                'show_comments': True, 'show_attendance': True,
                'show_position': True, 'show_skills': True,
                'show_next_term': True, 'watermark': 'none'}
    brands = {}
    batch = []
    pairs = Score.objects.using(db).filter(is_published=True).order_by().values_list(
        'school_id', 'term_id').distinct().iterator(chunk_size=500)
    for school_id, term_id in pairs:
        if school_id not in brands:
            school = School.objects.using(db).get(pk=school_id)
            theme = school.theme_config or {}
            contact = ' | '.join(str(value).strip() for value in
                                 (school.address, school.phone, school.email) if str(value).strip())
            brands[school_id] = {
                'school_name': school.name, 'school_address': school.address,
                'school_phone': school.phone, 'school_email': school.email,
                'school_motto': school.motto, 'school_registration_number': school.registration_number,
                'school_contact_line': contact,
                'school_logo': school.logo if school.logo.startswith(('https://', 'http://')) else '',
                'document_primary_color': theme.get('primary_color') or '#173B56',
                'document_secondary_color': theme.get('secondary_color') or '#256D85',
                'document_accent_color': theme.get('accent_color') or '#D8A548',
            }
        batch.append(Style(school_id=school_id, term_id=term_id,
                           configuration=defaults.copy(), branding=brands[school_id]))
        if len(batch) == 500:
            Style.objects.using(db).bulk_create(batch, ignore_conflicts=True)
            batch.clear()
    if batch:
        Style.objects.using(db).bulk_create(batch, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ('results', '0003_scratchcard_revoked_at_scratchcard_revoked_by_and_more'),
        ('gradebook', '0003_term_scoring_and_review'),
    ]
    operations = [migrations.RunPython(snapshot_existing, migrations.RunPython.noop)]
