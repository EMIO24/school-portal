# Batch 26A institutional identifier hardening

Starting checkpoint: `f01f468ac578f012deff6d313930ab95a1f5533e`, branch
`complete-version`, clean worktree, 3 October 2026.

## Algorithm inventory before implementation

StudentProfile.save() fills a blank admission number using
generate_admission_number(); StaffProfile.save() fills a blank staff ID using
generate_staff_id(). Existing nonblank IDs are retained on ordinary saves.
Student and staff serializers create the user and profile inside an atomic
transaction. AdmissionDecision additionally locks its application row and
returns the admitted student on a repeated admit decision.

Both old helpers opened an atomic block, selected the last profile belonging to
the school by descending identifier text, locked that profile, parsed its final
hyphen-separated suffix and added one. Student IDs use uppercase full school
slug, current calendar year and a minimum four-digit sequence; staff IDs use
uppercase full slug, STAFF and a minimum four-digit sequence. Student sequences
restart by year; staff sequences do not. Both profile fields are globally unique.

The empty-school query locks no row. A standalone helper can also release its
lock before insertion. Concurrent queries can select the same latest row, then
calculate the same successor even after waiting for that row's lock. Text order
puts 9999 ahead of 10000. A malformed selected suffix silently restarted at one.
Distinct school slugs can normalize to the same uppercase global prefix.

School.slug allows 100 ASCII slug characters. Initial student IDs need 110
characters and staff IDs 111. Before this task the respective storage limits
were 128 and 30; sequence growth had no explicit bound.

## Invariants and architecture

- Retain the established format, globally unique profile fields, and tenant-bound
  profile creation and login lookups. Never rewrite an issued identifier.
- Reserve numeric sequences using an exact-prefix unique database counter row.
  The row exists before allocation; concurrent initial creation is serialized by
  its unique namespace, followed by SELECT FOR UPDATE and an atomic increment.
- Slugs with identical uppercase prefixes intentionally share a counter. Global
  issued-ID inspection returns only a numeric high-water mark, never a profile
  from another school. The school supplied to the existing creation workflow
  remains the owner of the new profile.
- Calculate the numeric maximum across matching issued IDs and durable counter
  reservations. This supports legacy IDs and later imports, handles 9999/10000
  correctly, and never reuses a committed reservation after a failed insert or deletion.
  Explicit custom nonnumeric suffixes are retained and excluded from arithmetic.
- A standalone helper commits its reservation before returning. Inside an outer
  creation transaction, the counter lock is retained through insertion and
  released only when that transaction commits or rolls back. An allocation in a
  rolled-back outer transaction is not issued and can be reused. Gaps are acceptable;
  uniqueness and history take priority over contiguous numbering.
- Counters are independent of school deletion or slug edits. A changed prefix
  gets its own counter; returning to an old prefix resumes its high-water mark.
- Bound automatic sequences to the signed bigint range, failing closed on
  exhaustion. Maximum generated lengths are 125 for students and 126 for staff
  at a 100-character slug, a four-digit year, and 19 sequence digits. Both fields
  allow 128 characters. Staff storage is widened with a forward migration.
- Use PostgreSQL only as the concurrency authority; no external service needed.

## Validation

Environment: repository `.venv` Python, `config.settings.local`, local PostgreSQL
database `paideia_batch17_dev` at `127.0.0.1:5432`, role `b16qa`. Credentials are
not included in this report. Test connections are independent thread-local
connections with barriers and bounded lock/statement waits; concurrency cases
use TransactionTestCase and require PostgreSQL.

The clean baseline passed makemigrations --check. After the model changes that
check reported only the new counter model and staff-ID alteration. Forward
migration `0018_institutional_identifier_sequences` contains exactly CreateModel
and AlterField, preserves global uniqueness, has no data rewrite, and follows
0017. It applied successfully; makemigrations --check now returns No changes
detected, and migrate --check passes. Legacy sequence state is bootstrapped
numerically on first use, including other schools sharing the exact prefix.

The first targeted run had one fixture failure: the standalone staff serializer
lacked its required tenant request context. Correcting the fixture left
production serializers unchanged. Final targeted results: **15 tests PASS in
35.244 seconds**, including six PostgreSQL concurrency tests with no skips.
Evidence: `test-logs/batch26a-identifiers-targeted.txt` (local, ignored by Git).

```powershell
python manage.py test enrollment.test_identifier_hardening -v 2
python manage.py test enrollment.test_batch22_25_operations accounts.test_student_login enrollment.test_basic_completion enrollment.test_import_contracts attendance.test_batch21_presence -v 2
python manage.py test attendance.test_presence enrollment.test_batch22_25_operations curriculum.test_batch24_learning_delivery curriculum.test_batch17 accounts.test_student_login -v 2
python manage.py test -v 2
```

Affected admission/staff regressions: **49 tests PASS in 105.202 seconds**,
including staff imports and Batch 21 role-change coverage. Evidence:
`test-logs/batch26a-admission-staff-regression.txt`.

Concentrated historical gate: **47 tests PASS in 87.601 seconds**. Evidence:
`test-logs/batch26a-concentrated.txt`.

The 15 targeted cases cover simultaneous first admissions (synchronized at
allocation), four later concurrent admissions, simultaneous decisions on one
application with a single audit/history, three concurrent staff API creations
(synchronized at allocation), committed helper reservations followed by delayed
insertion, normalized-slug cross-school races, numeric legacy bootstrap through
9999/10000 for both types, later imports/custom IDs, initial and maximum-bigint
staff length/password behavior, ordinary saves and slug changes, reservation
retention after deletion, fail-closed capacity exhaustion, normalized-prefix
legacy ownership, and student year rollover.

Full PostgreSQL regression: **538 tests PASS in 1268.861 seconds**, with no skips
or failures. Evidence: `test-logs/batch26a-full-backend.txt`. The existing
performance ceilings pass, including the parent dashboard at 16 queries and
teaching delivery at 5 queries for both 1 and 21 slots. The pre-existing Windows
WeasyPrint external-library warnings remain nonblocking for the test run;
native PDF rendering still needs verification in the release environment.

PostgreSQL schema inspection confirmed staff_id length 128. sqlmigrate shows only
the unique counter table and the staff varchar widening, with no data rewrite.
No old tests, skips, permission expectations, historical assertions or query
ceilings were modified. No password-hasher overrides were introduced.

Frontend production code is unchanged; its 54-suite/363-test
baseline and successful production build are retained without unnecessary reruns.
This report covers identifier hardening only; the rest of Batch 26 remains in progress.

## Operational boundaries

Keep the counter table in database backups/restores and leave old counters intact
when changing school configuration. Forward deployment is additive. Downgrading
to the old generator or shrinking staff storage after issuing longer IDs is not
a safe identifier-preserving rollback; use a reviewed recovery plan.

The numeric maximum is calculated in PostgreSQL over identifiers matching the
exact prefix; no whole-repository scan or Python-side profile loading occurs.
This also detects already-committed supplied numeric IDs. An external bulk SQL
writer that bypasses allocation and races to supply an already-reserved ID is
outside the automatic generator contract; database uniqueness still rejects the
collision. Institutional import paths generate IDs and already reject supplied
admission_number/staff_id columns. Raw SQL/QuerySet.update can likewise bypass
model history conventions; they are not introduced as application paths here.

## Remaining Batch 26 work

The scoped generator concurrency, numeric ordering, normalized-prefix collision,
staff storage and ordinary-save stability defects are covered by this change.
Identifiers explicitly supplied outside allocation remain subject to the existing
database uniqueness constraint; no existing custom identifiers are rewritten.

Adversarial tenant/permission matrices, welfare privacy, finance retries,
campus/learning-history security, migration/recovery drills, and browser/pilot
acceptance remain separate Batch 26 work. A follow-up recovery drill should prove
counter high-water marks survive a complete snapshot and restore. The existing
PostgreSQL backup implementation uses full-database pg_dump, including this table.
AdmissionApplication's independent random UUID-derived application-number
generator is unchanged; a rare UUID-prefix collision has no controlled retry.
No broader welfare/privacy hardening is included.

## Final change audit

- `backend/enrollment/utils.py`: replace latest-profile allocation with locked
  durable counters, exact numeric suffix aggregation and fail-closed capacity.
- `backend/enrollment/models.py`: add counter state and widen staff_id only;
  existing profile save behavior and all issued values remain unchanged.
- `backend/enrollment/migrations/0018_institutional_identifier_sequences.py`:
  forward counter creation and staff storage widening only.
- `backend/enrollment/test_identifier_hardening.py`: 15 new history, length,
  numeric sequence, ownership and PostgreSQL concurrency regressions.
- `docs/BATCH26A_IDENTIFIER_HARDENING.md`: design, migration, evidence and limits.
- `docs/BATCH21_25_VERIFICATION.md`: link the historical baseline to this report.

The reviewed checkpoint excludes logs, secrets, environment files, database
dumps, generated artifacts and unrelated changes. Only complete-version is a
commit/push target. Protected local ref remains
`a35c67e893d728449a0bda71fe9597413a8ebcd3`; read-only remote inspection recorded
`ca9f307a5c93afd657ccee1f5f44fe1dcde6b73f` for production-readiness-check.
