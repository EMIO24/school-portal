# Batch 26 hardening

Batch 26A checkpoint: `947c60449680966a6e07413ec63efbc4104355b2`.
Batch 26B starts from that clean checkpoint on `complete-version`, 3 October 2026.
Batches 21-25 remain the frozen functional baseline; Batch 26 is not complete.

## Batch 26B inventory and required matrix

TenantMiddleware resolves a school from X-School-Slug/subdomain. A selected header
is not authorization: enrollment.operations._school_user additionally requires
an authenticated active user, completed password change, matching school_id and
an explicitly allowed server-side role. Welfare uses these checks rather than
the wider subject-assignment helper in accounts.school_access.

| Role | Welfare | Admissions/documents/student records | Campuses |
| --- | --- | --- | --- |
| School admin | Own tenant, all categories, create/read/append/state | Own tenant | Own tenant |
| Principal | Own tenant, all categories, create/read/append/state | Own tenant | Denied by existing campus policy |
| Class teacher | Ordinary categories; currently delegated class and case's recorded class must match | Denied | Denied |
| Ordinary teacher | Denied, including a homeroom FK without class_teacher role | Denied | Denied |
| Parent/student | Denied, including linked parent/own student | Denied | Denied |
| Platform/superadmin | No implicit internal-school welfare authority | Denied | Denied |
| Foreign-school user or forged tenant selection | Denied regardless of otherwise privileged role | Denied | Denied |

The existing welfare routes are GET/POST operations/welfare/ and POST
operations/welfare/<case>/updates/. There is no case detail GET, case PATCH or
WelfareUpdate edit/delete route. Update POST appends a note and optionally changes
case status among open, monitoring and resolved; repeated notes are separate
attributable history, not an idempotency contract.

WelfareCase already stores class_arm_snapshot with PROTECT, and reports
student/class, category, severity, status, reporting/resolution actors, timestamps
and ordered follow-ups. WelfareUpdate stores note, status_after, author and time.
No notes appear in audit metadata. Student transfers preserve SessionEnrollment
periods and update current_class without modifying the welfare class reference.

Risks identified before changes:

- WelfareUpdateView SELECT FOR UPDATE includes nullable current-class and class
  snapshot joins. PostgreSQL must reproduce the actual write path before repair.
- Teacher list/update scope follows student.current_class only. Moving a student
  gives the new class teacher access to earlier ordinary-case history even when
  its recorded class differs. Require both current delegation and original class.
- Verify follow-ups/state changes never erase notes, resolution metadata remains
  coherent, and concurrent appends/transitions are serialized on the case row.
- Exercise object IDs and forged tenant headers separately; tenant selection
  cannot grant another school's user's role authority.

## Batch 26B findings and fixes

The first dedicated PostgreSQL run discovered 30 tests and failed with 3 failures
and 19 errors (including category subtests). The actual follow-up path raised
`NotSupportedError: FOR UPDATE cannot be applied to the nullable side of an outer
join`. Own-school cases with deliberately inconsistent foreign student/class
relations were disclosed, and a local StudentProfile linked to a foreign account
was accepted for creation. One new test incorrectly assumed missing tenant
selection must return 400: middleware deliberately leaves tenant=None and the
view denies it with 403. Its assertion now checks exactly 403 for missing and
404 for unknown selection; no authorization expectation was weakened.

Only enrollment/operations.py production logic changes:

- A welfare-only queryset applies the case, student, account and historical-class
  tenant checks before selecting cases or prefetching their private follow-ups.
- Class-teacher scope requires the explicit role, a current class equal to the
  recorded case class, and that class's current teacher delegation. Health and
  safeguarding are excluded from both list and update lookup. Out-of-scope case
  IDs now return 404; disallowed roles still return 403.
- Creation rejects foreign or inconsistent student/account/current-class links,
  and takes tenant, reporter and historical class from server-side context.
- Follow-ups retain transaction.atomic and use select_for_update(of=("self",))
  to serialize on the intended case row without locking nullable joined rows.
- Each update audit includes update_id, status_before and the existing final
  status, actor, school and student context. Private note contents remain absent.

There are no model, migration, shared role-helper or frontend changes. No new
product endpoints or idempotency contract were introduced.

## Historical and concurrent behavior

Real transfer_student execution preserves the original case's protected class
reference, details and the source SessionEnrollment class/session/period, while
creating destination membership and assigning the current class. Management can
still read old cases with their original class. Neither the old teacher after
transfer nor the destination teacher can list or update that old case. New cases
use the destination class; the former teacher cannot read or update them.
Changing teacher delegation within the recorded/current class immediately revokes
the previous teacher's access without rewriting the reporter or old case.

Follow-ups remain append-only through the API: monitoring, resolution and reopening
append distinct notes with authors, timestamps and status_after. PATCH/DELETE on
the update collection are rejected; no individual update edit route exists.
Earlier notes and original details remain unchanged. Reopening clears resolution
metadata; resolution records its actor/time.

Three TransactionTestCase scenarios use independent PostgreSQL connections,
thread barriers and real authenticated API requests: two notes, a state-neutral
note racing resolution, and duplicate resolution requests. Both updates survive
each race. Audit entries match each update's author, identifier and consecutive
status chain. A note without explicit status reads the locked case's current
status, so it cannot reopen a concurrently resolved case. Duplicate resolution
notes are allowed and attributable; the second does not replace the first
resolution actor.

## Tenant and permission evidence

The 27 ordinary tests plus three concurrency tests cover management access,
ordinary-category teacher access, wrong-class and sensitive-case denial, ordinary
teacher/linked parent/student/platform/anonymous denial, foreign object IDs,
forged tenant selection and payload ownership fields, corrupt cross-school
relations, invalid updates, append-only history, actual transfer and revoked
delegation. No skips, expected failures or broad exception swallowing were added.

New institutional spot-checks cover foreign admissions list/class/campus references,
student-record writes and foreign supersession, campus reads/patch/delete and
tenant spoofing, and role boundaries for those endpoints. Existing operations
tests already cover foreign admission-document IDs and foreign admission decision
and record-read IDs; those checks were retained and run without duplication.
Account privacy coverage additionally exercises school access, staff/student
demographics, parent relationships, results/documents and assigned-teacher access.

## Validation

Executed with the worktree's virtualenv, config.settings.local and the local real
PostgreSQL database. Test logs are local ignored evidence, not committed files.

- Dedicated module: **30 PASS in 8.510 seconds**;
  test-logs/batch26b-targeted.txt.
- Existing operations/presence/role regression: **24 PASS in 34.717 seconds**;
  test-logs/batch26b-existing-regression.txt.
- Concentrated security gate: **67 PASS in 50.307 seconds**;
  test-logs/batch26b-concentrated.txt. Modules: enrollment.test_batch26b_security,
  enrollment.test_batch22_25_operations, attendance.test_presence,
  attendance.test_batch21_presence, accounts.test_privacy.
- Full backend: **568 PASS in 1320.792 seconds**, no skips or expected failures;
  test-logs/batch26b-full-backend.txt. Mandatory because welfare tenant filters
  changed. The known optional WeasyPrint native-library warning remains visible
  and did not fail the suite.
- Schema checks: **PASS**; makemigrations --check reports no changes and
  migrate --check exits successfully; test-logs/batch26b-schema.txt.
- Frontend: **NOT RERUN**, because no frontend production code changed.

## Remaining Batch 26 work and limits

Batch 26 is not complete. Finance concurrency/retry hardening, campus-history
hardening, learning-resource security, migration/recovery drills and browser/pilot
acceptance remain separate work. Native PDF libraries still require validation
in the release environment; the known local WeasyPrint diagnostic is not hidden.

This checkpoint checks case history through class transfers, not an immutable
text snapshot of class/session names under renaming. It does not claim a full
fees/results/CBT tenant matrix or serialization against concurrent teacher
delegation changes. Corrupt historical rows fail closed rather than being
automatically repaired or deleted.

## Change audit and branch safety

Reviewed files: backend/enrollment/operations.py (scope/locking/audit fix),
backend/enrollment/test_batch26b_security.py (30 adversarial tests), and this report.
No pre-existing tests were edited. No credentials, environment/database files,
logs or unrelated changes are included.

Work is exclusively on complete-version. Protected production-readiness-check
references at the start are local a35c67e893d728449a0bda71fe9597413a8ebcd3 and
remote ca9f307a5c93afd657ccee1f5f44fe1dcde6b73f; these must remain unchanged.
All validation gates passed. Only the three reviewed files are to be staged for
`fix(batch26): harden tenant and welfare boundaries`, then pushed exclusively to
origin/complete-version without force. Post-push HEAD/remote equality, protected
branch references and a clean worktree are required and reported with the final
checkpoint SHA. No subsequent Batch 26 work is started at this checkpoint.
