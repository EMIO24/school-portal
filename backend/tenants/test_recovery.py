from contextlib import closing
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import SimpleTestCase
from django.core.management.base import CommandError
from .recovery import create_backup, restore_backup, verify_backup

class RecoveryTests(SimpleTestCase):
    def test_snapshot_restores_two_schools_uploads_and_does_not_overwrite(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.sqlite3'
            with closing(sqlite3.connect(source)) as db, db:
                db.executescript("CREATE TABLE tenants_school(id INTEGER PRIMARY KEY, name TEXT); INSERT INTO tenants_school VALUES(1,'A'),(2,'B'); CREATE TABLE accounts_customuser(id INTEGER PRIMARY KEY, school_id INTEGER REFERENCES tenants_school(id)); INSERT INTO accounts_customuser VALUES(1,1),(2,2); CREATE TABLE django_migrations(id INTEGER PRIMARY KEY); INSERT INTO django_migrations VALUES(1);")
            config = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(source)}
            media = root / 'uploads'; media.mkdir(); (media / 'report.pdf').write_bytes(b'%PDF-test')
            backup = root / 'backup'
            create_backup(backup, config=config, media=media)
            with closing(sqlite3.connect(source)) as db, db:
                db.execute("UPDATE tenants_school SET name='Changed' WHERE id=1")
            dest = root / 'restore.sqlite3'
            counts = restore_backup(backup, destination=dest, media_destination=root/'restored-media', config=config)
            self.assertEqual(counts['tenants_school'], 2)
            with closing(sqlite3.connect(dest)) as db:
                self.assertEqual(db.execute('SELECT name FROM tenants_school WHERE id=1').fetchone()[0], 'A')
            with closing(sqlite3.connect(source)) as db, db:
                self.assertEqual(db.execute('SELECT name FROM tenants_school WHERE id=1').fetchone()[0], 'Changed')
            self.assertEqual((root/'restored-media/report.pdf').read_bytes(), b'%PDF-test')
            with self.assertRaises(CommandError):
                restore_backup(backup, destination=source, media_destination=root/'new-media', config=config)
            with self.assertRaises(CommandError):
                restore_backup(backup, destination=dest, media_destination=root/'new-media', config=config)
            (backup/'database.sqlite3').write_bytes(b'corrupt')
            with self.assertRaises(CommandError):
                verify_backup(backup)

    def test_manifest_cannot_escape_backup_directory(self):
        with TemporaryDirectory() as directory:
            root = Path(directory); (root/'manifest.json').write_text(json.dumps({'version':1, 'database':'database.sqlite3', 'files':{'database.sqlite3':'bad','../secret':'bad'}}))
            with self.assertRaises(CommandError): verify_backup(root)
