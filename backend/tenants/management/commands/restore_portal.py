import json
from django.core.management.base import BaseCommand
from tenants.recovery import restore_backup

class Command(BaseCommand):
    help = 'Restore a trusted backup to a NEW database and NEW media directory only.'
    def add_arguments(self, parser):
        parser.add_argument('--backup', required=True)
        parser.add_argument('--destination')
        parser.add_argument('--database')
        parser.add_argument('--media-destination', required=True)
    def handle(self, *args, **options):
        result = restore_backup(options['backup'], options['destination'], options['database'], options['media_destination'])
        self.stdout.write(self.style.SUCCESS('Recovery drill passed: ' + json.dumps(result)))
