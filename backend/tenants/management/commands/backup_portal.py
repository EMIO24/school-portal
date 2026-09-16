from django.core.management.base import BaseCommand
from tenants.recovery import create_backup

class Command(BaseCommand):
    help = 'Back up the configured database and local uploads into a new directory.'
    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)
    def handle(self, *args, **options):
        result = create_backup(options['output'])
        self.stdout.write(self.style.SUCCESS('Backup verified: ' + str(len(result['files'])) + ' files. Store securely; keep encryption keys separately.'))
