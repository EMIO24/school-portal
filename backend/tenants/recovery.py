"""Portable database snapshots and non-overwriting recovery drills."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from django.conf import settings
from django.core.management.base import CommandError


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def pg_environment(config):
    env = os.environ.copy()
    for key, value in [('PGHOST', config.get('HOST')), ('PGPORT', config.get('PORT')),
                       ('PGUSER', config.get('USER')), ('PGPASSWORD', config.get('PASSWORD')),
                       ('PGSSLMODE', config.get('OPTIONS', {}).get('sslmode')),
                       ('PGSSLROOTCERT', config.get('OPTIONS', {}).get('sslrootcert'))]:
        if value:
            env[key] = str(value)
    return env


def run_pg(args, config):
    try:
        result = subprocess.run(args, env=pg_environment(config), capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise CommandError('Install PostgreSQL client tools (pg_dump/pg_restore) on PATH.')
    if result.returncode:
        raise CommandError('PostgreSQL backup/restore failed. Check database permissions, connectivity and client version.')
    return result


def create_backup(output, config=None, media=None):
    config = config or settings.DATABASES['default']
    output = Path(output).resolve()
    media = Path(media or settings.MEDIA_ROOT).resolve()
    if output == media or media in output.parents:
        raise CommandError('Backups must be stored outside the media directory.')
    if output.exists():
        raise CommandError('Choose a new backup directory; existing backups are never overwritten.')
    output.mkdir(parents=True, mode=0o700)
    engine = config['ENGINE']
    if engine.endswith('sqlite3'):
        source = Path(config['NAME']).resolve()
        if not source.is_file():
            raise CommandError('SQLite backup requires a persistent database file.')
        db_file = output / 'database.sqlite3'
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(db_file)) as dest:
            src.backup(dest)
            if dest.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise CommandError('Snapshot failed its SQLite integrity check.')
    elif engine.endswith('postgresql') or engine.endswith('postgresql_psycopg2'):
        db_file = output / 'database.dump'
        run_pg(['pg_dump', '--format=custom', '--no-password', '--file=' + str(db_file), '--dbname=' + str(config['NAME'])], config)
        run_pg(['pg_restore', '--list', str(db_file)], config)
    else:
        raise CommandError('Only SQLite and PostgreSQL are supported.')
    if media.is_dir():
        for source in media.rglob('*'):
            if source.is_symlink():
                raise CommandError('Media symlinks are not included. Copy their data into managed storage first.')
            if source.is_file():
                dest = output / 'media' / source.relative_to(media)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
    files = {p.relative_to(output).as_posix(): digest(p) for p in output.rglob('*') if p.is_file()}
    manifest = {'version': 1, 'engine': engine, 'database': db_file.name, 'created_at': datetime.now(timezone.utc).isoformat(),
        'files': files, 'mfa_key_fingerprint': hashlib.sha256(str(getattr(settings, 'PLATFORM_MFA_KEY', '')).encode()).hexdigest(),
        'media_scope': 'Local MEDIA_ROOT files only; back up cloud-hosted assets separately.'}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def verify_backup(backup):
    root = Path(backup).resolve()
    try:
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        if manifest['version'] != 1 or manifest['database'] not in ('database.sqlite3', 'database.dump'):
            raise ValueError('format')
        if manifest['database'] not in manifest['files']:
            raise ValueError('missing database')
        for name, expected in manifest['files'].items():
            path = (root / name).resolve()
            if root not in path.parents or not path.is_file() or digest(path) != expected:
                raise ValueError('checksum or path')
    except (OSError, ValueError, KeyError, TypeError):
        raise CommandError('Backup verification failed: missing file, unsafe path or checksum mismatch.')
    return manifest


def restore_backup(backup, destination=None, database=None, media_destination=None, config=None):
    config = config or settings.DATABASES['default']
    root = Path(backup).resolve()
    manifest = verify_backup(root)
    if not media_destination:
        raise CommandError('Choose a new --media-destination for restored uploads.')
    media_target = Path(media_destination).resolve()
    if media_target.exists():
        raise CommandError('Media destination already exists. Choose a new directory.')
    if manifest['database'] == 'database.sqlite3':
        if not destination:
            raise CommandError('Choose a new --destination SQLite file.')
        target = Path(destination).resolve()
        if target.exists() or target == Path(str(config['NAME'])).resolve():
            raise CommandError('Cannot restore over an existing or configured database.')
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents overwriting if another process creates the path.
        with target.open('xb') as output, (root / manifest['database']).open('rb') as source:
            shutil.copyfileobj(source, output)
        with closing(sqlite3.connect(target)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
                raise CommandError('Restored database failed integrity or foreign-key checks.')
            counts = {table: db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0] for table in
                      ['tenants_school', 'accounts_customuser', 'django_migrations']}
    else:
        import re
        import psycopg2
        from psycopg2 import sql
        if not database or not re.fullmatch(r'portal_restore_[a-z0-9_]+', database) or database == config['NAME']:
            raise CommandError('Use a new database name starting with portal_restore_. The configured database cannot be overwritten.')
        options = config.get('OPTIONS', {})
        connection = psycopg2.connect(dbname=config['NAME'], user=config.get('USER') or None,
            password=config.get('PASSWORD') or None, host=config.get('HOST') or None, port=config.get('PORT') or None,
            **{k: v for k, v in options.items() if k in ('sslmode', 'sslrootcert')})
        try:
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
        finally:
            connection.close()
        run_pg(['pg_restore', '--exit-on-error', '--no-owner', '--no-acl', '--no-password', '--dbname=' + database,
                str(root / manifest['database'])], config)
        restored = psycopg2.connect(dbname=database, user=config.get('USER') or None,
            password=config.get('PASSWORD') or None, host=config.get('HOST') or None, port=config.get('PORT') or None,
            **{k: v for k, v in options.items() if k in ('sslmode', 'sslrootcert')})
        try:
            with restored.cursor() as cursor:
                counts = {}
                for table in ['tenants_school', 'accounts_customuser', 'django_migrations']:
                    cursor.execute(sql.SQL('SELECT COUNT(*) FROM {}').format(sql.Identifier(table)))
                    counts[table] = cursor.fetchone()[0]
        finally:
            restored.close()
    media_target.mkdir(parents=True, mode=0o700)
    for name in manifest['files']:
        if name.startswith('media/'):
            relative = Path(name).relative_to('media')
            dest = (media_target / relative).resolve()
            if media_target not in dest.parents:
                raise CommandError('Unsafe media path.')
            dest.parent.mkdir(parents=True, exist_ok=True)
            with dest.open('xb') as output, (root / name).open('rb') as source:
                shutil.copyfileobj(source, output)
    return counts
