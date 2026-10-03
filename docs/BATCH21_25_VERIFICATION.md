# Batch 21–25 verification and Batch 26 entry

Identifier/concurrency follow-up: [Batch 26A identifier hardening](BATCH26A_IDENTIFIER_HARDENING.md).
The baseline results below remain historical evidence for checkpoint `f01f468`;
the follow-up report records the subsequent architecture, migration and rerun results.

Verified on 3 October 2026 in `C:\Users\user\school-portal-complete`.
Branch: `complete-version`. Base commit: `d933406615f1b1f558d5624926f8600a858b905b`.
The original results apply to this base commit plus the reviewed verification fixes. The checkpoint audit and subsequent admission fix are recorded below.

## Repository orientation

- Fast-forwarded the initially clean worktree from `c64c639` by 183 commits.
- Batch 21 checkpoint `9a65743` is an ancestor; 102 subsequent commits cover admissions/documents/records, welfare, learning delivery, and campus/class structure.
- `main` and `commercial-transformation` are ancestors of `complete-version`.
- Ahead/behind counts against remote branches: `main` 585/0, `commercial-transformation` 500/0, `commercial-readiness` 539/5, `production-readiness-check` 517/4.
- `production-readiness-check` was inspected only. Its local ref remains `a35c67e893d728449a0bda71fe9597413a8ebcd3`.

## Gates

| Gate | Result |
| --- | --- |
| Model/migration drift | PASS: no changes detected |
| PostgreSQL migrations | PASS: applied, final `migrate --check` passes |
| Concentrated backend | PASS: 33 tests, 37.958 seconds |
| Full PostgreSQL backend | PASS: 521 tests, 1160.556 seconds |
| Frontend | PASS: 54 suites, 363 tests, 36.856 seconds |
| Production build | PASS with nonblocking warnings |
| Patch whitespace | PASS: `git diff --check` |

Backend gates used `config.settings.local` and the authorized local PostgreSQL database. No test exclusions or password-hasher overrides were introduced.

Evidence is in `test-logs/concentrated-gate.txt`, `test-logs/backend-20261003-074421.txt` (the archived 521-test run), `test-logs/frontend-latest.txt`, and `test-logs/frontend-build-gate.txt`. These local logs are not release artifacts and future runs may overwrite them.

## Fixes verified

- Removed the deleted `operations` app's stale registration and corrected the class-teacher query's Python argument order.
- Restricted admission, clock-out, and presence-correction locks to the row being updated, retaining atomic transactions and tenant filters.
- Serialized the date in the presence correction's before-state audit snapshot.
- Restored the public branding field allowlist; authenticated setup still exposes class-arm configuration.
- Combined dashboard score and ledger aggregates. The measured parent dashboard returned to its existing 16-query ceiling; the ceiling was not raised.
- Repaired Admissions JSX and omitted unchanged roles from staff-edit payloads. A new frontend test verifies that an explicitly selected role change is still sent.
- Supplied arrival evidence in older lateness fixtures; preserved historical membership, retry, result, and finance assertions. Added historical date/class assertions to the backdated correction test.
- Corrected the attendance mock's daily mode, awaited loaded presence settings, and disambiguated the record-history selector.
- Kept the staff identity fixture focused on identity/activation preservation; Batch 21's explicit administrator role-change tests pass.

## Batch 26 starting checks

The regression baseline is green and eligible for a Batch 21–25 freeze after review of these local fixes. Batch 26 release hardening can begin; it is not complete.

1. Admission-number storage and login length are resolved by this checkpoint (details below). Sequential identifier concurrency, sequence ordering beyond 9999, and the analogous staff-ID length issue remain Batch 26 work.
2. Add PostgreSQL coverage for welfare updates, particularly nullable joins in their lock query, privacy boundaries, and historical class snapshots. The nullable-join risk is inferred from the verified admission/presence failures; welfare updates were not independently reproduced here.
3. Exercise simultaneous admission decisions and retries, confirming one student, one historical enrollment, one institutional record, and consistent audit events.
4. Complete browser and pilot-school journeys across admissions, welfare, campuses, learning delivery, and ledger-backed finance.
5. Review the hook dependency warnings in StudentRecords/StudentPresence. The tooling `fs.F_OK` deprecation is harmless to the successful build.
6. Verify native PDF rendering in the release environment: this Windows run emitted missing-library WeasyPrint messages while the PDF regression tests passed.

The original verification run made no commits or pushes. This report accompanies the reviewed checkpoint on `complete-version`; no deployment is included.

## Checkpoint audit, 3 October 2026

Batches 21–25 regression verification passed. Batch 26 release hardening remains in progress.

Starting HEAD: `d933406615f1b1f558d5624926f8600a858b905b`. All pre-existing changes were reviewed; no unrelated files were found. No assertions, tenant-isolation cases, historical-integrity checks, skips, expected failures, or query ceilings were removed or relaxed. The dashboard ceiling remains 16 queries.

### File-by-file classification

Paths below are relative to the repository root.

| File | Classification and purpose |
| --- | --- |
| `backend/accounts/school_access.py` | Startup: valid positional Q argument order; tenant predicate retained. |
| `backend/accounts/views.py` | Performance: combine equivalent score and ledger aggregates. |
| `backend/attendance/views.py` | Locking/concurrency and auditing: lock presence row only; serialize audit date; atomic scope and tenant checks retained. |
| `backend/config/settings/base.py` | Startup: remove registration for nonexistent operations app; operation endpoints live in enrollment. |
| `backend/enrollment/operations.py` | Locking/concurrency: lock admission row without nullable joined rows; preserve atomic decision and retry behavior. |
| `backend/tenants/serializers.py` | Privacy/security: restore existing public branding allowlist, as asserted in accounts privacy tests. |
| `frontend/src/pages/admin/Admissions.jsx` | Frontend regression: close JSX expression. |
| `frontend/src/pages/admin/StaffForm.jsx` | Frontend regression: omit unchanged role, preserve explicit role changes, label role selector. |
| `backend/attendance/test_transfer_membership.py` | Test: provide required arrival evidence and add historical presence assertions. |
| `backend/curriculum/test_batch24_learning_delivery.py` | Test: explicit valid admission identifier isolates learning-resource behavior. The generator defect is now covered separately. |
| `backend/enrollment/test_basic_completion.py` | Test: remove contradictory role-change input from identity/activation test; preserve role/password/assignment assertions. Authorized promotions remain covered in attendance/test_batch21_presence.py. |
| `backend/enrollment/test_operations.py` | Test: supply required late-arrival evidence; journey assertions retained. |
| `backend/tenants/test_commercial_simulation.py` | Test: supply late-arrival evidence; retry and performance thresholds retained. |
| `frontend/src/__tests__/pages/BasicCompletion.test.js` | Test: add explicit role-change coverage. |
| `frontend/src/__tests__/pages/Batch22To25.test.js` | Test: disambiguate visible record heading without removing history assertions. |
| `frontend/src/__tests__/pages/StudentPresence.test.js` | Test: await loaded settings and assert heading semantically. |
| `frontend/src/__tests__/pages/TakeAttendance.test.js` | Test: include daily mode in realistic session fixture. |
| `backend/enrollment/models.py` | Admission hardening: widen student admission storage to 128. |
| `backend/enrollment/migrations/0017_widen_student_admission_number.py` | Admission hardening: single non-destructive AlterField; unique constraint retained. |
| `backend/accounts/serializers.py` | Admission hardening: align login admission-number input limit with storage; authentication and tenant predicates unchanged. |
| `backend/enrollment/test_batch22_25_operations.py` | Test: maximum-slug admission, distinct sequential identifiers, retry, historical enrollment/record counts, and identifier preservation. |
| `backend/accounts/test_student_login.py` | Test: long generated number disambiguates duplicate student names; wrong name still denied. |
| `docs/BATCH21_25_VERIFICATION.md` | Documentation: evidence, complete change audit, identifier investigation, remaining hardening. |

### Admission identifier investigation

- `StudentProfile.save()` calls `enrollment/utils.py:generate_admission_number()` only when the number is blank. The unchanged format is uppercase full school slug, year, and a minimum four-digit sequence. A maximum 100-character slug produces 110 characters for sequences 1–9999. The sequence has no explicit upper bound; 128 characters leaves 22 sequence digits with a four-digit year. This is capacity headroom, not a new sequence guarantee.
- Earlier migrations 0001/0004 and the pre-fix PostgreSQL schema define varchar(30). Migration 0017 only widens that column to varchar(128), retaining global uniqueness. No data migration, truncation, identifier rewrite, or format change occurs. PostgreSQL rejects overlength inserts rather than silently truncating them.
- StudentProfileSerializer exposes the number read-only; there is no enrollment form override. LoginSerializer previously capped the optional disambiguator at 50; it now accepts 128. The student-name backend still filters by tenant, active student, name and password. Result lookup does not impose a smaller limit. Repository searches found no other admission-number input length constraint.
- AdmissionApplication uses a separate `ADM-` plus 12 hex-character UUID prefix (16 characters, column limit 20). Its unique constraint rejects a random collision; collision retry is not added here. StudentRecordEntry references the student and stores application references in unrestricted text, so needs no alteration.
- Existing admission numbers remain unchanged on later profile saves and repeated admission decisions. New regression coverage exercises these paths and checks one enrollment and institutional record per admitted application.
- Separate remaining risks: the generator locks the latest row, which does not serialize an empty-school first admission; its transaction can end before the caller inserts. Lexical sorting also does not reliably select the largest sequence after 9999. Case-normalized school slugs can conflict with global number uniqueness. These were not introduced or resolved by widening storage and require adversarial concurrency/history work before release.
- StaffProfile has an analogous independent 30-character staff-ID field, while its full-slug format can need 111 characters before sequence growth. That field is not changed in this student-admission migration; record it for Batch 26 identifier hardening.

### Checkpoint validation

Environment: local PostgreSQL at `127.0.0.1:5432`, database `paideia_batch17_dev`, role `b16qa`, settings `config.settings.local`, repository `.venv` Python. Credentials are not recorded here.

- Before generating migration: `python manage.py makemigrations --check` returned `No changes detected`.
- After generating migration: the same check returned `No changes detected`; `python manage.py migrate` applied only enrollment 0017; `python manage.py migrate --check` passed. A direct information_schema query confirmed admission_number length 128.
- The first new regression run failed because the test changed slug but not the subdomain used by tenant resolution. The fixtures now update both; production tenant-resolution code was unchanged.
Commands for the new checks (run from backend with the environment above):

```powershell
python manage.py test enrollment.test_batch22_25_operations.Batch22To25OperationsTests.test_long_slug_admission_preserves_identifiers_and_retry_history accounts.test_student_login.StudentNameLoginTests.test_long_generated_admission_number_disambiguates_name_login -v 2
python manage.py test attendance.test_presence enrollment.test_batch22_25_operations curriculum.test_batch24_learning_delivery curriculum.test_batch17 accounts.test_student_login -v 2
```

The schema/identifier change needs the admission and concentrated gates; the login field-length adjustment additionally needs the full student-login module. No authentication backend, permission utility, shared infrastructure, or frontend code changed after the previous verified baseline, so the 521-test full backend, 54-suite/363-test frontend, and successful production build are retained from that run. The login module covers cross-school names, inactive accounts, ambiguous names, wrong credentials, legacy email login, and MFA behavior.

Before the checkpoint push, read-only remote inspection recorded `production-readiness-check` at `ca9f307a5c93afd657ccee1f5f44fe1dcde6b73f`; its separate local branch remains at `a35c67e893d728449a0bda71fe9597413a8ebcd3`. Neither is a push target.

Final checkpoint results: exact new regressions PASS (2 tests, 13.790 seconds); concentrated backend plus student-login module PASS (47 tests, 89.425 seconds: 34 concentrated and 13 login). Evidence: `test-logs/checkpoint-admission-targeted.txt` and `test-logs/checkpoint-concentrated-gate.txt`. Schema PASS. Frontend/build not rerun because unchanged since their verified baseline. Final diff audit found no unrelated files, secrets, conflict markers, logs, databases, environment files, or build artifacts in the intended checkpoint.
