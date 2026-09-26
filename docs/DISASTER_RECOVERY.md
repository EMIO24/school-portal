# Paideia disaster recovery runbook

This runbook is for authorized deployment operators. A real Railway PostgreSQL backup and restore has already been completed and verified; do not repeat a production restore merely as a test. Never enable `RESET_DB_ON_DEPLOY` during backup or recovery.

## Recovery objectives and ownership

- The platform owner declares an incident and names one recovery operator and one reviewer.
- RPO and RTO are internal targets **to be finalized after production usage and backup frequency are established**. Do not present them as customer guarantees.
- Repository evidence does not establish Railway backup frequency or retention. **Confirm Railway backup/retention configuration before commercial launch.**
- Store backups outside Git in encrypted, access-controlled storage. Keep encryption keys separately and apply the retention policy agreed by the platform owner.

## Current capability and operating decision

Checkpoint A verified one production PostgreSQL logical dump, its checksum, an
isolated restore, and representative Django reads. That proves the restore path,
not a recurring backup schedule. Railway platform snapshot creation was unavailable
to the current operator, and no automated production backup has been verified.
Railway [documents daily, weekly and monthly volume backup schedules](https://docs.railway.com/volumes/backups),
but an operator with project backup permissions must confirm and enable the schedule
in the PostgreSQL service's Backups tab. A Railway volume backup restores within
the same project and environment; retain a separate off-platform logical copy.

Before real customer data accumulates, the platform owner must choose a controlled
encrypted off-platform destination, approve a retention policy, and assign a person
to check every backup run. A practical **proposed**, not yet implemented, policy is
daily copies for seven days, weekly copies for four weeks, and monthly copies for
three months; legal and commercial retention requirements may change it. Until an
approved schedule or external runner exists, an operator must run section A
manually at the agreed cadence and record a missed run as an incident. A scheduled
logical runner is possible only with a private secret store, encrypted external
storage, failure alerts, and an approved recurring cost. None is provisioned here.

| Responsibility | Current owner |
| --- | --- |
| Approve storage, retention and a production restore | Platform owner |
| Run backup, verify checksum/archive and transfer off-platform | Authorized recovery operator |
| Check backup failures, age and storage access each day | Authorized recovery operator |
| Restore into an isolated database and validate Django reads | Recovery operator, reviewed by platform owner |
| Decide whether production writes stop or recovery begins | Platform owner |

The platform owner and recovery operator may be the same person at this stage, but
the incident record must name who performed each step. The owner should arrange a
second reviewer for a production restore where practical.

## A. Create and verify a database backup

Prerequisites: authorized Railway access, PostgreSQL client tools compatible with the server (`pg_dump` and `pg_restore`), sufficient encrypted local space, and the deployed application environment. Supply `DATABASE_URL` only through Railway's environment or a private shell environment; never place it in a command, document, terminal transcript, or Git file.

1. Create a new UTC-named directory; the command refuses to overwrite one:

   ```bash
   stamp=$(date -u +%Y%m%dT%H%M%SZ)
   python manage.py backup_portal --output ".backups/paideia-${stamp}"
   ```

2. Confirm `.backups/paideia-<UTC>/database.dump` and `manifest.json` exist and are non-empty. The command also runs `pg_restore --list` and records SHA-256 checksums before reporting success.
3. Inspect only archive structure when needed: `pg_restore --list .backups/paideia-<UTC>/database.dump`. Do not dump table contents to logs.
4. Move the complete directory to approved encrypted storage, restrict access, record its UTC timestamp and checksum, and remove unencrypted temporary copies after verification.

The backup command includes local `MEDIA_ROOT` files. Its manifest states that cloud-hosted media must be backed up separately. The documented `.backups/` and `.restores/` directories are ignored by Git, but operators must still check `git status` before committing.

## B. Test restore

Use an isolated environment and a new database. Never point application traffic at it during validation.

```bash
python manage.py restore_portal \
  --backup ".backups/paideia-<UTC>" \
  --database "portal_restore_<incident_or_date>" \
  --media-destination ".restores/media-<UTC>"
```

The command verifies checksums, requires a new database name beginning with `portal_restore_`, refuses the configured database, restores with `--no-owner --no-acl --exit-on-error`, and refuses an existing media destination. Point a temporary restricted application instance at the restored database for the verification checklist below. Delete the drill resources only after evidence is recorded.

## C. Production restore safety gate

A production restore is an incident operation and is never executed by this runbook automatically. Before an authorized database administrator executes the reviewed provider-specific restore plan:

1. Identify and record the incident, impact, operator, reviewer, and decision time.
2. Confirm the chosen backup, its UTC timestamp, checksum, and archive listing.
3. Take and verify a fresh emergency backup when the database is reachable.
4. Independently confirm the target project, environment, database host, and database name without recording credentials.
5. Restrict writes or place the application in maintenance mode as the incident requires.
6. Test the backup in a new isolated database first whenever possible.
7. Execute the approved restore using compatible PostgreSQL tooling or Railway's documented restore facility.
8. Run migrations only when the restored schema and the selected application commit require them; review the migration plan first.
9. Complete database and application verification below.
10. Restore access gradually, monitor errors, and record completion and any data-loss window.

Never use `RESET_DB_ON_DEPLOY`; it flushes data and is unrelated to recovery.

For every incident, record: detection time and symptom; affected services and last
safe write time; who restricted writes; backup timestamp, source and SHA-256; archive
listing result; isolated restore database and validation results; chosen application
commit and migration plan; owner approval and reviewer; production restore start/end;
health, authentication, tenant, academic and payment-read checks; estimated data-loss
window; and follow-up owner. Never include credentials or personal records.

## D. Incident playbooks

### Accidental data deletion

Stop the responsible write path, preserve logs, take an emergency backup, establish the deletion time, select the last verified backup before it, and test-restore it. Prefer a reviewed, narrowly scoped data repair when referential integrity can be proven. Use the production restore gate only when full recovery is necessary.

### Failed deployment

If the database is healthy, roll back application code rather than restoring data. Identify the last known-good commit, review migrations introduced after it, and use Railway's rollback/redeploy facility or deploy that immutable commit. Do not reverse an applied migration until its data effects are understood. Verify health, authentication, tenant isolation, and affected workflows.

### Database corruption or unavailability

Restrict writes, inspect Railway/PostgreSQL status, preserve diagnostics without credentials or personal data, and determine whether availability, storage, or integrity failed. For availability failures, recover service through the provider first. For confirmed corruption, use the production restore gate and the newest verified backup that predates corruption.

## E. Post-recovery verification

Record aggregate results only; never log personal data.

- Application starts and `/health/` returns exactly `{"status":"ok"}`.
- `python manage.py showmigrations --plan` is consistent with the selected application commit; apply reviewed migrations only if required.
- Aggregate counts are plausible for schools, users, tenant relationships, academic sessions/terms, students/classes, `FeePayment`, and `PaymentOrder` records.
- Subscription plans and expiry state exist and match the recovery point.
- Platform owner and representative tenant authentication work.
- Requests cannot access another tenant's data.
- A representative school dashboard and critical academic records load.
- Payment history and receipts load without initiating a transaction.
- Background and provider configuration is present without printing secret values.
- Error logs remain stable before write access is restored.

Record the backup timestamp, restored application commit, migration state, aggregate checks, test results, access restoration time, and follow-up owner in the incident record.
