from django.core.management.base import BaseCommand
from django.db import transaction
from gradebook.models import ScoreEntry
from tenants.models import PlatformEvent

class Command(BaseCommand):
    help = 'List incorrect stored grades; --apply corrects them with an audit event.'
    def add_arguments(self, parser):
        parser.add_argument('--school', type=int, required=True)
        parser.add_argument('--apply', action='store_true')
    @transaction.atomic
    def handle(self, *args, **options):
        rows = ScoreEntry.objects.filter(school_id=options['school']).select_related('school')
        count = 0
        for row in rows.iterator():
            grade, remark = row.resolve_grade()
            if grade == row.grade and remark == row.remark: continue
            count += 1
            self.stdout.write(f'Entry {row.pk}: {row.grade} -> {grade}')
            if options['apply']:
                PlatformEvent.objects.create(action='school.grade_corrected', target=str(row.pk), details={'school_id':row.school_id,'old_grade':row.grade,'new_grade':grade,'total':str(row.total_score)})
                row.save()
        self.stdout.write(f'{count} affected entries. '+('Corrections applied.' if options['apply'] else 'Review before running --apply.'))
