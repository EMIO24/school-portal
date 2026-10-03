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

## Batch 26C: finance, campus history and learning-resource security

Starts from clean, fetched `aefd23b1028239d75cc863ffa89d64e4365594fe` on
complete-version, 3 October 2026. Batch 26 remains incomplete.

### Inventory and contracts

Student fee settlement is atomic: payments.settle locks School, then PaymentOrder;
ledger.record_payment_entry also locks School and the finance account. Manual
payments and charge/adjustment generation use that same school lock. PaymentOrder
references are unique; StudentLedgerEntry has a one-to-one FeePayment relation,
frozen charge uniqueness and retry-key constraints. Allocations link each credit
to a frozen charge. Online amounts come from prepare_online_charge and stored
allocations, with provider reference/amount/currency/mode/email validation.
Paystack is an external payment provider, never the balance source of truth.

Signed webhooks re-verify with the provider and call the same settlement path as
browser verification. External calls are mocked in tests; PostgreSQL writes,
transactions, independent thread connections and API authorization are real.

FeePayment already stores receipt_snapshot at creation, including school identity,
theme, student/class, category, term/session, amount, date, method and issuer.
Current FeeSchedule values or current balance must not rewrite these facts.
Verified opening balances deliberately encompass historical pre-cutover receipts;
those receipts must not be converted into new credits during a retry.

Campus has an existing conditional unique constraint allowing at most one primary
campus per school. ClassArm, StaffProfile and AdmissionApplication campus FKs use
PROTECT. Deactivation is an operational flag, not deletion or reassignment.
Nullable legacy campuses and separate no-arm defaults per campus remain supported.
Create remains Enterprise-only; campus writes remain school-admin-only.

AcademicResource is explicitly reusable institutional content scoped to school,
class level and subject, without a class-arm or session field. Its workflow is
draft -> submitted -> reviewed -> approved; revision is a new draft linked through
supersedes, preserving the approved original. Teachers use SubjectAssignment scope;
school admins can author institutional content; principals review and approve but
cannot become revision authors. Parents have no resource endpoint authority.
Students see approved materials for their current level, including older approved
revisions, subject to subject/class relevance. These are not session-specific
lesson plans. This checkpoint preserves that existing learner policy and does not
add a historical student browsing endpoint or grant arbitrary past-class access.

### Reproduced failures and fixes

Dedicated tests ran before broader regressions. Initial fixture mistakes were
corrected without weakening invariants: Python dates rather than date strings for
SessionEnrollment.clean, an explicitly backdated auto_now_add admission_date before
transfer, and valid class-arm lengths/qualification choices. The red run after
initial date corrections had 9 failures and 3 errors across 30 tests, including
remaining fixture issues; production defects reproduced included:

- Successful-order verification and manual retry reported success despite a
  missing ledger credit. Completed fee orders now validate receipt count, unique
  schedules, amounts, matching ledger credits and allocation totals. Drift moves
  the order to review without new receipts or credits. A reference with existing
  receipts cannot create another posting even if its saved status is pending.
- Successful browser verification rechecks local integrity under the settlement
  lock without another provider call. Manual retry returns 409 on inconsistent
  credit; another payment is blocked while unreconciled receipts exist. Verified
  opening balances retain the deliberate pre-cutover exception, with old receipt
  facts left intact.
- Concurrent primary-campus PATCH raised PostgreSQL UniqueViolation. Campus
  create/PATCH/delete are now atomic and serialize on the School row; the existing
  primary constraint remains unchanged as a database backstop.
- Deleting an admission-only referenced campus raised ProtectedError. It now
  returns 409, retaining all references, as class/staff-reference deletion already
  did. No protected history is detached or deleted.
- New class and admission placement accepted an inactive campus. Class/staff
  serializers reject new inactive assignments while allowing unrelated edits to
  existing historical assignments. Admission class resolution checks implicit
  preferences, class-campus links and no-arm default campuses for active local
  ownership. No nullable-campus requirement is added.
- Principal revision could create principal-authored teacher work. Revision now
  denies that role while retaining principal review/approval and admin authorship.
- An owning teacher could submit a draft after assignment revocation. Resource
  transitions now check assignment before acting, alongside create/revise checks.
- Corrupt resource/student relations exposed inappropriate content. Resource
  querysets constrain level/subject/standard school relations, assignment checks
  constrain their tenant relations, and student access validates profile/class
  ownership. Explicit subject-to-level mappings are respected; legacy subjects
  without mappings remain compatible.

No models/migrations or frontend production files change. No existing assertions,
skips or expected failures are edited.

### Validation matrix

| Area | Required outcome |
| --- | --- |
| Same-reference settlement race | One receipt, credit, allocation and verified audit |
| Signed webhook retry / webhook plus verify race | One financial effect |
| Manual plus online full payment race | One accepted payment; competing operation denied/reviewed |
| Distinct partial manual/online race | Both valid payments retained, no excess credit |
| Client amount manipulation | Frozen obligation retained; excess payment rejected |
| Missing ledger / allocation / prior-reference receipt | Review or 409, no automatic credit recreation |
| Receipt after schedule/class/branding/balance changes | Original snapshot unchanged |
| Foreign tenant reference/receipt | Denied before provider invocation or financial writes |
| Referenced campus deletion / deactivation | Conflict on deletion; references still resolve |
| Inactive/new or foreign placements | Rejected; historical assignment edits still permitted |
| Concurrent primary changes | Both requests complete; exactly one primary remains |
| Enterprise and no-arm/null campuses | Gate retained; campus defaults distinct and retry-safe |
| Teacher resource authorship | Assigned level/subject only; revoked scope denied |
| Principal | Review/approve, no author/revision-author escalation |
| Student/parent | Approved relevant materials only / parent denied |
| Approved resource mutation/revision | Original content/link/scope/approval preserved; new draft only |
| Class transfer and session change | Source enrollment and approved original preserved; current-level learner scope |

Dedicated modules: fees.test_batch26c_finance, tenants.test_batch26c_campus_history,
curriculum.test_batch26c_resource_security. Added tests also check loss of allocations
and a pre-existing receipt under a pending reference, beyond missing-credit drift.

Targeted: **32 PASS in 47.601 seconds**; test-logs/batch26c-targeted.txt.
Concentrated: **97 PASS in 198.043 seconds**; test-logs/batch26c-concentrated.txt.
The gate includes all three dedicated modules, fees.test_ledger, fees.test_batch17h,
fees.test_invoice_payments, enrollment.test_batch22_25_operations,
curriculum.test_batch24_learning_delivery, curriculum.test_batch17, plus eight
existing Paystack tests for retry/receipts, frozen charges, provider mismatch,
webhook retries, malformed allocations, order kinds, changed balances and foreign
student/payer relations. No skips or expected failures.

Full backend: **600 PASS in 1430.920 seconds**, no skips or expected failures;
test-logs/batch26c-full-backend.txt. Mandatory due to shared finance and resource
workflow fixes. Known local WeasyPrint native-library diagnostics remain visible
without failing tests; no separate native PDF validation was started.
Schema: **PASS**; makemigrations --check reports no changes, migrate --check exits
successfully; test-logs/batch26c-schema.txt. No migrations are required.
Frontend: NOT RERUN, because no frontend production code changes.

### Limits and remaining work

This is not an automatic financial-recovery tool. Drift leaves money/history
untouched for explicit review; legacy cutover remains a separate accounting
contract. Primary-campus concurrency is exercised; retirement racing every
placement/import path is not claimed. Resources remain reusable level/subject
content, not session snapshots; session-specific execution history remains in
lesson plans and SessionEnrollment. Current configuration must not rewrite those
existing rows. No broader learning feature is added.

Recovery drills, native PDF validation, browser acceptance and pilot-school
acceptance remain outside this checkpoint. Do not start them automatically.

### Batch 26C final audit and checkpoint boundary

Reviewed production changes:

- backend/fees/ledger.py: receipt-to-credit integrity predicate only.
- backend/fees/payments.py: validate completed postings, reject existing-reference
  reposting, and verify local completed orders without an external request.
- backend/fees/views.py: manual retry and missing-credit guards, preserving the
  explicit verified-opening treatment of pre-cutover receipts.
- backend/tenants/campuses.py: atomic school lock for writes and protected-delete
  conflict handling; Enterprise gating, tenant permissions and DB constraints stay.
- backend/enrollment/serializers.py and staff_serializers.py: inactive-campus
  denial for new assignment, preserving unrelated historical-assignment edits.
- backend/enrollment/class_structure.py: active, own-school campus validation for
  admissions and implicit defaults.
- backend/curriculum/learning.py: tenant-consistent resource/assignment queries,
  transition scope checks, principal revision-author denial and learner filtering.

Three new dedicated test modules and this appended report are the other reviewed
files. No existing test file, model, migration, frontend file, environment file,
database, log or unrelated file is staged. Fixtures use unusable passwords and an
explicitly fake test-only Paystack key. No real secrets are added.

Financial amounts still follow frozen obligations and the ledger; no provider or
browser balance authority is introduced. Campus deletion remains protected,
Enterprise creation stays gated, teacher scope is narrowed, and unapproved
resources stay hidden. Approved resource and payment/receipt facts are preserved.

All gates passed before staging. Commit intent:
`fix(batch26): harden finance campus and learning history` on complete-version,
with a normal push to that branch only. Local/remote checkpoint equality, clean
worktree and unchanged protected branch references are verified after push and
reported with the checkpoint SHA. Batch 26 is not declared complete and no
recovery, native PDF, browser or pilot acceptance work follows this checkpoint.

## Batch 26D - recovery, retry and campus retirement races

Starting checkpoint: `fc28f96b97c97c4f7f79587f3d1621779678b7e4` on
`complete-version`. Only that branch is eligible for the checkpoint push.
The protected local and remote `production-readiness-check` references must
remain unchanged. This phase adds no models, migrations or frontend changes.

### Recovery findings and changes

- Admission decisions already lock the application and reuse its admitted
  student. They now acquire the school lock first, preventing retirement from
  racing a destination lookup. Completed admission replay checks its own-school
  student, admission enrollment and application-specific institutional record.
  Missing companion history returns 409 without reconstructing records.
- Migration Centre already has source references, account identities, chunk
  school locks and row savepoints. Tests interrupt the second row after its
  writes, then retry the same student, staff, teaching-assignment, parent-link
  and fee-schedule files. Successful rows are reused; interrupted rows roll back
  and can be created once. Parent account replay does not duplicate the parent.
  Existing terminal job row provenance remains the original attempt's evidence;
  retry responses report the current attempt's CREATE/REUSE/REJECT outcomes.
- Legacy student CSV has no durable source reference. Its old name/DOB/class
  check could miss a previously imported student after a class change, and it
  ran outside the write transaction. The locked row transaction now rejects a
  matching name/DOB independently of current class, requiring explicit review
  or Migration Centre references. It does not guess that two people are equal.
  Implicit no-arm classes are created inside that same rollback boundary.
- Promotion retries reuse one staged decision and preserve the source placement.
  Concurrent requests serialize on the existing school lock. Placement is still
  applied only by rollover. Repeated decision saves retain the existing
  intentional decision audit events rather than creating more promotion rows.
- Rollover retains its atomic cutover and school lock. Completed replay now
  validates the saved student snapshot, closed source enrollment, recorded
  decision and original destination placement. Missing history fails closed
  with `RolloverSafetyError`; no history is invented. Retired destinations are
  rejected before creating a new placement. A failure at the final audit write
  rolls back enrollment changes and current session flags together.
- Result publish and reopen retries preserve one audit per actual transition.
  Concurrent publish/reopen requests leave scores unchanged and finish in draft
  after reopening; publication either replays before reopening or rejects its
  invalid state afterward. Existing permissions and reason requirements remain.
- Presence arrival replay preserves its first arrival. An identical timestamp
  correction now returns the existing record without another audit or rewriting
  the first correction reason. Real corrections retain the existing audit path.

### Campus retirement ordering

Campus retirement already locks the school. Operational class/student/staff
writes now use the same lock before related-object validation. Default-class
resolution, admission, current enrollment and transfer services lock the school
before student/class rows and recheck database state rather than cached campus
or current-session flags. Staff campus assignments, class scopes and teaching
assignments reject new destinations on inactive campuses. Teaching assignment
replay and unrelated edits to existing retired-campus records remain possible.

PostgreSQL tests hold the retirement school lock with the inactive update still
uncommitted, start an independent worker connection, observe its database
boundary via `pg_stat_activity`, and commit retirement before allowing placement
to proceed. The worker must reject the retired destination and leave no new
placement. Covered paths are staff campus assignment, staff class assignment,
single teaching assignment, class creation, admission, cached no-arm default
creation, transfer and initial current-session placement. Existing Batch 26C
tests also preserve references and allow unrelated edits after retirement.

### Validation

Executed with Windows PowerShell, Django and PostgreSQL; no simulated results.
New modules: `enrollment.test_batch26d_recovery` and
`tenants.test_batch26d_campus_races`. The initial run reproduced the retirement
races and unsafe missing-history/stale-session replay behavior before fixes.
No existing tests were weakened; no skips or expected failures were added.

- Dedicated targeted gate: 32 PASS. Expanded recovery/identifier rerun:
  47 PASS (186.888 seconds; the 32 dedicated tests plus all 15 identifier tests).
- Concentrated gate: 193 PASS (1017.499 seconds).
- Full backend gate: 632 PASS (1569.379 seconds); no skips or expected failures.
- Schema: PASS (`makemigrations --check`, `migrate --check`). No migration needed.
- Frontend: NOT RERUN; no frontend production code changed.

Concentrated labels include both dedicated modules, enrollment operations,
migration, current enrollment and transfer tests, promotion tests, rollover
execution/preview/safety, Batch 26C campus history, presence/attendance reports,
academic result workflow and Batch 26C finance idempotency tests. Test logs stay
ignored and are not included in the commit.

The first full run exposed two identifier test harness barriers inside ID
allocation. With the new school lock, the first request waits at that barrier
while the second correctly waits for the school lock, making the barrier
impossible to satisfy. Those two API tests now use their existing independent
connection/request-start barrier. All ID suffix, count, ownership, password and
institutional-history assertions are retained. Direct concurrent allocator
reservation tests are unchanged. The broad run was interrupted, the identifier
module added to the targeted gate, and the full suite restarted after that gate.
The concentrated gate preceded this test-harness adjustment; production code
was unchanged, and the final full run includes both the concentrated cases and
the adjusted identifier cases. Optional WeasyPrint native-library warnings remain
non-blocking; this checkpoint does not claim native PDF validation.

Final review includes the placement lock helper, enrollment/class/assignment
services and API serializers/views, admission replay checks, rollover replay
checks, presence correction replay, the two dedicated test modules, the two
identifier harness adjustments and this report. No model, migration, frontend,
environment, log or database dump is staged. Commit intent:
`fix(batch26): harden recovery retries and campus retirement races`.

### Limits and remaining work

Legacy CSV name/DOB collisions deliberately require review; they are not a
durable identity or automatic reconciliation mechanism. Migration Centre
terminal job metadata remains a record of the original attempt, not a new
persisted per-attempt retry timeline. Completed admission/rollover corruption
requires explicit review and is not silently repaired. Arbitrary manual database
writes are outside the operational API locking contract.

Traffic protection, native PDF validation, browser acceptance and pilot-school
acceptance remain separate checkpoints. Batch 26 is not declared complete.
Stop after the reviewed commit, normal complete-version push and post-push
verification; do not start those remaining phases automatically.
