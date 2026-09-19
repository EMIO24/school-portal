# Backups, recovery and production setup

## Local test backup and restore

Run these commands from the project directory. Use new output names for each run: existing backups and databases are never overwritten.

```powershell
python backend/manage.py backup_portal --settings=config.settings.integration --output .backups/my-test-backup
python backend/manage.py restore_portal --settings=config.settings.integration --backup .backups/my-test-backup --destination .restores/my-test.sqlite3 --media-destination .restores/my-test-media
```

The backup includes the entire database (all schools) and files under local `MEDIA_ROOT`, plus a SHA-256 manifest. Restoration validates all files, checks SQLite integrity and foreign keys, and reports school, user and migration counts. It does not switch the running application to the restored database.

The completed local drill is in `.backups/platform-security` and `.restores/platform-security.sqlite3`. It restored 3 schools, 17 accounts and 74 migration records. Automated tests additionally verify upload restoration, cross-school data preservation, corruption detection and refusal to overwrite the source.

## Production prerequisites

- Install the updated backend requirements and run database migrations for the target environment.
- Generate a dedicated Fernet key for `PLATFORM_MFA_KEY`, store it in the hosting environment's secret configuration, and retain a secure separate copy. Do not use the test settings key in production.
- Generate a key once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep it stable: replacing it without re-encrypting enrolled authenticator secrets prevents verification.
- Preserve the deployment settings and required secrets separately from database backups. The manifest contains only an MFA-key fingerprint, never the key itself. Restored MFA secrets require the original key.
- Require HTTPS for public login and signup. Keep the production database and backup storage private.

## PostgreSQL backup and restore drill

Use the environment's normal Django settings, with `pg_dump` and `pg_restore` installed on PATH. The account needs permission to create the isolated restore database for a drill.

```text
python backend/manage.py backup_portal --output .backups/production-drill
python backend/manage.py restore_portal --backup .backups/production-drill --database portal_restore_drill --media-destination .restores/production-drill-media
```

Only a new database whose name starts with `portal_restore_` is allowed. The command never drops, cleans or replaces the live database. Database credentials are passed through the subprocess environment rather than command-line arguments. Use only trusted backups.

CI now exercises PostgreSQL backup and restoration with two distinct schools. This CI step has been added but not executed in this local session because Docker and PostgreSQL client tools were unavailable. A PostgreSQL production restore is not yet certified by local testing.

## Operating schedule

Configure the production host's scheduler to run the backup command daily with a unique timestamped output directory. Upload completed backups to private storage with encryption and retention enabled; a copy on the same server is not sufficient recovery protection. Keep at least seven daily copies and four weekly copies as an initial policy, and run a restoration drill monthly. These production scheduler/storage settings are not configured by the local commands.

Back up Cloudinary or other remotely stored assets using that provider's backup/export process: the command copies only local uploads. Quiesce upload writes when a database snapshot and file copy must represent the same point in time. Plan storage-level snapshots or PostgreSQL point-in-time recovery separately for a production recovery objective shorter than the backup interval.

After restoring, test owner MFA login, both schools' account isolation, student records and representative uploaded files before a separately planned application cutover. Never test by overwriting the live database.

## Implementation references

Authenticator handling follows [PyOTP's documentation](https://pyauth.github.io/pyotp/), including code replay rejection and throttling. Secrets use [Fernet authenticated encryption](https://cryptography.io/en/latest/fernet/). SQLite uses the [online backup API](https://docs.python.org/3/library/sqlite3.html#sqlite3.Connection.backup); PostgreSQL uses [custom-format pg_dump archives](https://www.postgresql.org/docs/current/app-pgdump.html).
