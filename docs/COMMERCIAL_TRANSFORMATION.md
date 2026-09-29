# Paideia working map

Baseline: production `a35c67e`; implementation branch `commercial-transformation`.
`complete-version` is preserved separately. Its divergent migration history is
not a deployment source. Reuse its ideas only after reviewing production compatibility.

## Architecture and reuse

- Backend: Django/DRF domain apps, PostgreSQL, JWT authentication, role permissions,
  tenant middleware and scoped querysets. Owner MFA and platform audit events exist.
- Frontend: React 18/CRA, React Router, Axios, Auth/Theme contexts and shared portal
  navigation/workspace CSS. Existing pages remain the implementation foundation.
- Academics/results: sessions, terms, classes, teacher assignments, fixed assessment
  fields, school grading, published-score locking/reopening and PDFs exist.
- Attendance/fees: tenant-scoped attendance, summaries, manual payments, receipts
  and balances exist. Verify each workflow rather than assuming commercial completeness.
- Payments: server verification, signed webhooks, reconciliation, idempotent
  settlement and exception operations exist; preserve these controls.
- CBT: question bank, DOCX import, exam sessions and marking exist.
- Analytics/notifications: snapshot tasks and durable notification outbox exist;
  shared worker/Beat requirements need commercial cost review.
- Branding: ten validated semantic-token presets, school identity and a tenant-scoped
  appearance preview/save exist after Batch 9; draft/publish and document styling
  remain separate capabilities.
- Deployment: Docker/Railway backend and Vercel proxy fixes preserved. Legacy CI
  targets main and includes Cloudflare deployment; align release automation before launch.
- Testing: baseline system/migration checks and 51 selected readiness tests passed;
  frontend production build passed. This is not a complete release certification.

## Gaps and priorities

- P0: preserve tenant/privacy/payment protections and migration history. Never enable
  the existing reset switch during transformation; production is assumed populated.
- P1: immutable term invoices, subscription lifecycle, owner billing visibility,
  centralized student lifecycle, configurable assessments and guided onboarding.
- Improve: imports, mobile parent workflows, result layouts, consistent shared UI.
- Build later: necessary Enterprise institutional workflows; no speculative integrations.
- Deferred: full accounting, native apps, payroll and other excluded product lines.

## Batch 1: plan and billing foundation

Enterprise is accepted by owner plan controls, model validation, subscription offer
administration, checkout and settlement. It inherits currently shipped Premium
capabilities; this does not claim that multi-campus/custom workflows already exist.
Free remains the existing setup state. Existing Basic entitlements are preserved;
splitting standard imports from advanced operations and notifications from automation
requires separate workflow work before the target matrix is complete.

Public defaults: Basic NGN 800, Premium NGN 1,500, Enterprise NGN 2,500 per enrolled
active student per term. At 100+ students, the shared quote applies 10% automatically.
Existing configured offers are preserved; school-specific negotiated prices are not
global defaults. Quotes and checkout use `fees.billing.subscription_quote`.

`fees.billing.active_students` scopes `StudentProfile.status='active'` to the school.
Login deactivation does not itself withdraw enrollment. Withdrawn/graduated students
are excluded; additional lifecycle states will need an explicit migration/workflow.
Money calculations use Decimal, with totals rounded to two places. Legacy numeric
JSON fields remain compatible with existing consumers.

New migrations only extend plan choices and create a missing Enterprise offer.
They do not rewrite existing migrations, overwrite offers or create school data.
The explicit bootstrap retains its atomic get-or-create behavior for all three plans.
Reversing the data migration deliberately preserves commercial configuration.

## Batch 2: immutable term invoices and lifecycle

`fees.TermInvoice` records the school, academic session, term, names at issue time,
plan, enrolled active count, snapshot timestamp, standard/effective rates, discount,
subtotal/final amount, currency, invoice number, issue/due dates and grace days.
Generation consumes the existing billing service and configured SubscriptionOffer;
later enrollment, plan, offer or calendar changes do not recalculate issued records.
Amounts are Decimal and invoice API money fields are decimal strings. Effective
rates retain four decimal places; final totals preserve checkout rounding.

Migration `fees.0010` adds one table, protected foreign keys, lifecycle constraints,
an index and uniqueness on `(school, term, billing_context)`. A term determines its
academic session. Generation locks the school row on PostgreSQL; repeated requests
return the existing invoice (HTTP 200 versus 201 for new issuance), even if it is
paid or void. Due date/plan changes in retries cannot replace its snapshot. Invoice
numbers are deterministic `PAI-` plus UUID5 of the school/term/subscription identity;
both displayed number and billing-period identity have database uniqueness.

Invoices issue immediately; there is no draft state. `issued` can transition to
`paid` or `void`; both are terminal. `overdue` is derived for unpaid invoices after
their due date, so no worker is required. Grace days are stored for future access
policy, not used to change the invoice due date or suspend schools in this batch.
The normal ORM manager blocks updates/deletion and instance saves cannot overwrite
issued records. Private lifecycle code changes only lifecycle fields under row locks.
Database administrators/direct SQL remain outside these application protections.

Endpoints:

- School admin GET `/api/fees/subscription/invoices/` and `/<id>/`: own school only,
  available through the existing billing exemption even after a plan downgrade.
- Owner GET `/api/platform/invoices/` and `/<id>/`: across schools; filters `school`,
  `plan`, `academic_session`, `term`, `status`; 50 rows per page using `page`.
- Owner POST collection: `school`, `term`, `due_date`, optional `grace_period_days`
  (0–365). The school determines the plan; client prices/statuses are rejected.
- Owner POST detail: `action: "void"`, `reason`; no arbitrary edits or deletes.

Issuance, voiding and payment transitions create PlatformEvent records. Platform
viewers, students, parents and teachers cannot access invoice operations. School
admins cannot generate/void invoices or retrieve another school's invoice by ID.

`record_invoice_payment` is a guarded service hook for later reconciliation:
requires a verified successful subscription PaymentOrder matching school, plan,
currency and exact amount, created/paid after the invoice snapshot. Payment linkage
is unique and repeated settlement is idempotent. It does not charge, extend a
subscription, call Paystack, expose a manual "paid" API or automatically attach
historical payments. Existing checkout/settlement behavior is unchanged.

Regression coverage includes persisted amounts for all 15 plan/count boundaries,
the intentional Basic 99-to-100 price drop, 102-to-99 enrollment changes, a fresh
next-term snapshot, custom-rate rounding, repeats/database uniqueness, immutable
ORM operations, valid/invalid lifecycle actions, owner filters and tenant attacks.
A two-connection PostgreSQL generation test is included; local SQLite runs skip it.
Local Docker was unavailable, so PostgreSQL concurrency verification remains a
pre-promotion gate. No production database or environment was modified.

The invoice payment hook above was the Batch 2 boundary. Batch 3 connects it to
checkout/verification as described below; no historical invoices are fabricated.

After invoices: Basic workflows, theme system, Premium hardening, necessary
Enterprise foundations, full school simulation, then release freeze and full checks.

## Batch 3: invoice payment and document workflow

New subscription checkout POST `/api/fees/subscription/` accepts only `invoice_id`.
The old plan-only checkout is no longer an initiation path. The quote GET remains
available for compatibility, but cannot determine an invoice charge. The server
uses the invoice amount/currency and snapshotted `subscription_months`, converts
Decimal to integer kobo, and binds the attempt using `PaymentOrder.invoice` plus
an invoice-specific reference prefix. Parent/student school-fee payments stay in
their existing FeePayment domain and cannot settle subscription invoices.

Per the commercial decision, successful invoice payment retains rolling-month
subscription extension, not academic-term-end coverage. Newly issued invoices
snapshot the configured offer duration. Existing invoices receive NULL duration
in additive migration `0011`; an owner must explicitly confirm it once through
POST `/api/platform/invoices/<id>/` with `action: "set_duration"` and `months`
(1–12) before checkout. The action is audited and only accepts unpaid legacy
invoices with no attempts. It does not infer historical terms or offer values.
Legacy unlinked payments still verify/settle using their saved amount/duration;
they are never automatically assigned to invoices. Their unfinished attempts must
be reconciled before another school subscription checkout begins.

Checkout/settlement/voiding now consistently lock school before payment/invoice.
A partial unique constraint prevents multiple initializing/pending attempts per
invoice; review attempts block new checkout in the service. Pending retries verify
and reuse the original checkout; verified failed/abandoned attempts allow a new
attempt. Ambiguous initialization/verification remains blocked for investigation.
Voiding is blocked while an attempt is initializing, pending or under review.

Trusted verification and signed webhooks use the existing settlement function.
Reference, amount, currency, provider mode, customer, invoice association, school,
plan, duration and payable status must agree. Mismatches become review cases;
no invoice or subscription credit is applied. Received amount/currency and the
verification timestamp are stored without provider credential payloads. Invoice
payment, paid status, audit event and one subscription extension commit together.
Repeated successful verification returns the settled order without extending again.

School subscription screens now provide paginated invoice cards, filters, detailed
pricing, payment history, safe checkout, verification and protected PDF downloads.
The existing owner Payments page includes cross-school invoice filtering and
expected/received amount visibility using existing reconciliation controls.
Owner duration confirmation handles legacy invoices. Interfaces include loading,
empty/error/retry states and responsive shared styles; no theme redesign was made.

School document endpoints append `invoice.pdf` or `receipt.pdf` to the invoice
detail URL; equivalent owner endpoints use `/api/platform/invoices/<id>/`.
Documents use saved school/calendar names and monetary snapshots. A receipt is
available only for a paid invoice with its verified payment link. Its stable number
is `RCP-<invoice number>`; repeat downloads never create additional receipt records.
WeasyPrint uses the new branded subscription template with no remote assets; the
existing text PDF utility is the fallback where native rendering is unavailable.
Document responses are authenticated, tenant scoped and marked no-store.

Verification: affected backend suite 128 passed, 0 failed, 2 PostgreSQL-only tests
skipped; frontend billing/platform/download suites 19 passed. After correcting an
effect-cleanup lint warning, all 6 invoice UI tests passed again and the production
frontend build compiled successfully with CI warnings treated as errors. Local invoice/receipt
PDF tests exercised the fallback because WeasyPrint native libraries are unavailable.
Before promotion verify the styled documents and responsive browser presentation
in the deployment-compatible environment.

**PRE-PROMOTION POSTGRESQL TEST REQUIRED**: invoice-generation and simultaneous
verification/webhook settlement tests must pass against disposable PostgreSQL.
Docker's local engine was unavailable; no installation/reconfiguration was attempted.
No production data, provider credentials, Railway settings or deployment was changed.

## Batch 4: Basic operations — safety and setup slice

Verified a connected fresh Basic-school API journey: identity, calendar, classes,
subjects, staff creation/initial password change, teacher assignment, student
creation, explicit parent linking, attendance, draft scores, administrator
publication, linked-parent results, manual part payment, balance and PDF receipt.
This uses the existing fixed assessment/default grading scheme. It does not certify
the complete Batch 4 target or browser/mobile acceptance.

Corrected tenant-relation validation for class arms, subject levels, assignments
and attendance creation. Bulk teacher assignment validates the whole replacement
before removing old assignments; the existing staff action now accepts the scoped
term/session contract. Attendance registers cannot be moved by generic PATCH;
teacher mutation checks include the term, and finalization counts active enrollment.
Published scores cannot be deleted through the portal. Student/staff deletion is
rejected in favor of status changes, and in-use academic configuration is retained.
Staff suspension/termination/resignation updates login access without deleting
assignments. Withdrawal preserves scores and remains excluded from billing counts.

Basic now includes the existing standard CSV imports through the central catalog;
CBT and other Premium features remain gated. Student imports validate optional
email, reject ambiguous/invalid arms, and report duplicate name/date/class rows.
An optional `class_arm` column disambiguates arms. Existing imports into a class
level with no arms still create an unassigned student. Row failures no longer expose
raw exception messages. The existing preview/confirm interface is reused.

New `/api/school/setup/` derives readiness without persistent wizard state and
permits only school identity/contact edits. `/admin/setup` adds identity/logo and
class creation, progress and links to existing operational screens. Logo uploads
reuse the existing validated storage service. Platform pricing/plan/theme controls
are excluded from this school endpoint.

Administrators explicitly grant/revoke parent links from a student's profile.
The endpoint scopes both sides to the school, reuses parent phone-login accounts,
rejects mismatched existing accounts and audits link changes using IDs. Guardian
contact fields alone grant no access. Parent OTP delivery still needs the existing
configured SMS service. Student photos now update the selected student's account
through validated server upload, fixing the former update to the administrator.

The class-scoped gradebook `entries/sheet/` returns the complete active class and
checks teacher/class/subject/term authorization. It fixes the 20-student truncation.
The teacher screen saves drafts for administrator review and no longer offers an
unauthorized publish action. The existing admin publication/reopening flow remains.

Verification: 18 new backend workflow/security tests passed during targeted work
and the broader run. The broader affected run discovered 178 tests: 175 passed,
2 PostgreSQL-only skips, and 1 import compatibility failure. After restoring the
unassigned import behavior, all 14 affected login/import retests passed. Frontend
affected suites: 21 passed. Django system and migration checks passed; no migration
or dependency was added. The production frontend build passed with CI warnings
treated as errors. Existing parent UI tests emit an act() warning but pass.

Remaining P1: configurable assessment structures with historical versioning;
validated grading edits; explicit submitted/reviewed state and missing-score
semantics; general student/staff account-name editing. Existing subject CA/exam
settings are not authoritative for the fixed gradebook and need the assessment
work before claiming custom splits are supported.
Remaining P2: selector pagination beyond the current first page, further import
validation UX, and hands-on responsive checks. Setup checks are operational aids,
not a launch-readiness certificate. Existing result templates/calculations are reused.

**PRE-PROMOTION POSTGRESQL TEST REQUIRED** remains for both invoice concurrency
tests. Styled invoice/receipt PDFs and responsive billing screens still require
deployment-compatible verification; local PDF tests use the supported fallback.
No Docker retries, production changes, merge or deployment were performed.

## Batch 4B: Assessment, grading and result lifecycle

The existing ScoreEntry gradebook now uses one school-owned configuration per
academic term (`TermScoring`), shared across that term's classes and subjects.
Components have stable keys, labels, positive Decimal maxima totaling 100, and an
assessment/examination classification for compatibility summaries. Grade ranges
cover 0–100 at the existing two-decimal precision without gaps or overlaps.
`/api/gradebook/configuration/?term=<id>` permits school-admin configuration;
the existing school setup page provides the editor and validated readiness checks.
No plan entitlement or Premium restriction changed: this is Basic functionality.

Configuration becomes immutable when scores exist; schools configure future terms
to change rules. Scores reference the protected configuration and store component
values, total, grade and remark. Missing marks remain missing, distinct from zero.
Calculation and grade lookup are centralized in `gradebook/scoring.py`; result
APIs, parent summaries, student results and PDF templates consume saved grades.
The teacher sheet and result outputs now display configured assessment components.
Legacy columns remain compatible. Additive migration `gradebook.0003` leaves
existing grades, totals and publication flags intact, with no invented historical
configuration or recalculation. Legacy writes can initialize validated defaults;
GET requests never create or recalculate academic records.

Class/subject/term transitions are draft → submitted → approved → published.
Teachers submit only assigned contexts; school administrators approve and publish
from Result Management. Transitions validate roster completeness and all marks,
lock school/score rows and commit the entire operation with its audit event.
Submitted/approved/published scores cannot be casually edited or deleted.
The existing reasoned, audited administrator reopen action restores draft status.
Published remarks and domain ratings also require reopening before correction.
Parent/student slip endpoints reject unpublished results and retain relationship
and tenant checks. Teacher score reads now require the exact subject/term assignment.

Verified three assessment structures (10/10/10/70, 20/20/60, 40/60), configured
grade boundaries, lifecycle, atomic rollback, publication privacy and stored-grade
history: a published 72/A stays A after a future term raises the A threshold to 75.
Targeted backend tests: 17 passed; broader academic/readiness suite: 69 passed,
0 failed. Frontend configuration/score-entry/setup tests: 10 passed. Django system
check and migration consistency check passed. The production frontend build passed
with CI warnings treated as errors after correcting one editor lint warning;
the six affected editor/score-entry tests passed again after the final UI changes.

Remaining Basic P1: general student/staff account-name editing. P2: selector
pagination, further import validation UX and hands-on responsive verification.
This batch does not certify the full Basic release or add result-template designs.
**PRE-PROMOTION POSTGRESQL TEST REQUIRED** remains for both skipped billing/payment
concurrency tests. Academic transaction tests here use SQLite; PostgreSQL lock
behavior still needs deployment-compatible verification. Styled invoice/receipt
PDFs, updated academic PDFs and responsive browser layouts remain manual promotion
checks; native WeasyPrint libraries are unavailable locally. No dependencies,
production-data changes, merge or deployment were introduced.


## Batch 4C: Basic account and operational completion

Student/staff identity edits update the existing account atomically and retain
passwords, generated identifiers, assignments and historical records. Access-state
changes retain records; staff on leave retain the existing access behavior. Parent
search, reuse, account editing and unlinking are school-admin scoped; unlinking
removes only that child's relationship. Account edits record field names, not
sensitive values, in the audit event. No plan entitlements changed.

Existing CSV preview/confirmation and per-row partial imports are reused. Invalid
student dates now return row errors instead of failing after earlier rows commit.
Duplicate headers, malformed rows, invalid emails and supplied identifier/tenant
columns are rejected. Identifiers remain generated; imports create new records.
Guardian contact data alone does not grant parent portal access.

Reference selectors load every page; student/staff directories stay paginated.
Teachers see their own paginated assignments. Session-aware term selection reduces
ambiguous academic context. Failed staff loads prevent saving; failed/incomplete
assignment loads prevent replacing existing assignments and offer retry. Existing
setup readiness and role navigation remain in place.

Verification: 13 focused backend tests passed. The broader Basic run had 172
passing tests, two PostgreSQL-only skips and one loader error from an incorrect
login test-module name. Running the correct accounts.test_student_login module
separately passed all 12 tests. Final staff leave-state regression passed separately.
Frontend: 32 tests passed in the broader targeted run; 13 passed after the final
loading protections (including two new cases), covering 34 distinct tests across
runs. The final seven BasicCompletion frontend tests also passed after the staff
leave-state confirmation correction. Django system and migration checks passed;
no new migrations/dependencies.
Production frontend build passed. These are local checks, not browser/device proof.

Measured SQLite directory baseline and 500-student fixture both used 3 SQL queries;
500 students still returned 20 rows per page. This demonstrates bounded response
size/query count, not production latency or concurrent-user capacity. Main JS build
was 315.07 kB gzip (about +1.74 kB); no production performance claim is made.

Remaining P2: CSV preview shows the first five rows and is not a server dry run;
richer migration/import validation remains separate. Hands-on desktop/tablet/mobile
and slow-network Basic journeys remain unverified. This slice does not certify the
entire Basic product. Next recommended batch: Commercial Simulation; not started.

**PRE-PROMOTION POSTGRESQL TEST REQUIRED** remains for both billing concurrency
tests and deployment-compatible transaction behavior. Styled invoice/receipt and
academic PDFs require native WeasyPrint verification; responsive billing and Basic
browser/device workflows remain promotion gates. No merge, push or deployment.

## Batch 5: Commercial Simulation

`python manage.py seed_commercial_simulation --confirm-development` creates a
deterministic engineering dataset and a separate boundary tenant. It refuses
production settings, requires explicit acknowledgement and never replaces an
existing simulation school. The primary school contains 505 students (500 active),
40 staff (25 teachers), 380 parents, 525 links, 18 class arms, 15 subjects, 91
current/historical assignments, 90 registers with 2,500 attendance records, 18 fee
schedules, 300 payments, 140 current/historical score entries and lifecycle-varied
results. The issued Basic invoice snapshots 500 active students at NGN 720 after
the established 10% discount, totaling NGN 360,000.

Integrated tests cover teacher attendance and result submission through publication,
historical locks, parent and student access, administrator fees, payment retry,
immutable billing and representative direct-ID attacks against the boundary tenant.
Confirmed P1 fixes exclude withdrawn students from new registers, replace the
low-attendance per-student query loop, make manual-payment retries idempotent, and
paginate debtors at 50 rows while preserving school-wide totals and full paged PDF
export. No pricing, entitlement, dependency or schema changes were made.

Local SQLite measurements at 500 active students: students 3 queries/20 rows,
staff 5/20, assignments 3/20, attendance 2/5, gradebook 7/28, results 2/28,
debtors 7/50, low attendance 2/230, parent children 4/2 and parent dashboard
12 queries. Observed response times were approximately 5-95 ms in the final broad
run; these are regression measurements, not PostgreSQL latency or capacity claims.
The broader affected suite passed 178 tests with two PostgreSQL-only skips. Django
and migration checks passed. Frontend payment/pagination regressions and the
production build passed after the final correction.

Remaining P2: richer server-side import dry runs, broader simulation distributions
and hands-on slow-network/mobile usability refinements.

### PostgreSQL promotion-gate validation — 2026-09-26

The two previously skipped concurrency tests ran against PostgreSQL 15.15 in an
isolated, disposable `postgres:15-alpine` Docker container on local port 55432.
Django used the development settings with a process-local database override, created
`test_school_portal_gate`, applied all migrations and destroyed the test database.

- `fees.test_invoices.InvoiceConcurrencyTests.test_simultaneous_generation_returns_one_invoice`
- `fees.test_invoice_payments.InvoiceSettlementConcurrencyTests.test_verification_and_webhook_settlement_race_has_one_effect`

Result: 2 tests run, 2 passed, 0 failed, 0 skipped. Concurrent invoice generation
returned one invoice and one issue audit event. The verification/webhook race applied
one payment association and one subscription extension, with no duplicate settlement.
No production code, repository configuration, production database or deployment was
changed; the disposable container was stopped after Django removed its test database.
The **PRE-PROMOTION POSTGRESQL TEST REQUIRED** gate is closed. Earlier markers above
remain as the chronological record of prior batches.

Native WeasyPrint invoice/receipt and academic PDF inspection, real browser/device
workflows, slow-network/mobile usability and deployment-compatible validation remain
promotion gates. Recommended next batch: release-gate validation; not started.

### Remaining release-gate validation — 2026-09-26

Validation used commit `6312a54`, an isolated integration SQLite database, a
disposable PostgreSQL 15 clone, the backend deployment Docker image and installed
headless Chrome. No production data, credentials or provider transactions were used.

The deployment image built successfully with its native Cairo/Pango libraries. Native
WeasyPrint produced a 14,599-byte subscription invoice, 14,658-byte payment receipt
and 19,150-byte academic result, each with a valid PDF header and response metadata.
Chrome visual inspection confirmed legible branding, identifiers, dates, amounts,
assessment rows, totals, grade, remarks and signatures without clipping or unintended
page breaks. The result calendar glyph is missing from the deployment font set; the
adjacent next-term date remains readable, so this is P2. The native invoice/receipt
and representative academic-result PDF gates are closed.

Real Chrome journeys covered administrator directories and academic/fee pages;
teacher attendance plus score draft, reload, submission; administrator approval and
publication; multi-child parent switching with each child's results and fees; and
student dashboard, results, attendance and fees. Direct student requests for an
unrelated student and the boundary tenant both returned 403. Student results and the
representative administrator, teacher and parent screens had no document overflow at
1440x900, 768x1024 or 390x844. The responsive gate is closed for these representative
workflows. Development service-worker MIME warnings did not affect navigation.

Administrator, teacher, parent and student journeys also passed with 350 ms latency,
90,000 bytes/s download and 45,000 bytes/s upload. Loading and navigation remained
recoverable. The fixture had no eligible `Record Payment` action, so the manual-payment
double-submit/retry UI was not exercised under throttling; the slow-network gate is
therefore only partially closed.

Deployment-compatible checks passed: backend image build and native PDF regression
(1 test, 1 passed), Django `check --deploy`, the repository `deployment_check` command,
migration drift check, optimized frontend build (315.56 kB gzip main JavaScript), and
the documented Railway `/health/` endpoint (HTTP 200, `{"status": "ok"}`). Authenticated
smoke testing on the deployed Railway/Vercel services was not performed without
authorized production test credentials, so this gate remains partially closed.

No P0 or P1 defect was found and no application code, schema, dependency, pricing or
entitlement changed. Remaining P2 evidence gaps are the throttled manual-payment UI,
authenticated deployed browser smoke testing, and the cosmetic result PDF glyph.
Release gates still require validation before Batch 6.

### Final Basic release-gate closure attempt — 2026-09-26

The manual-payment check used the isolated integration database, its authorized school
administrator, an active test student and an existing fee schedule with an outstanding
balance. Headless Chrome exercised the actual Fee Collection page and Django endpoint
with 350 ms latency, 90,000 bytes/s download and 45,000 bytes/s upload.

The normal action and populated form were visible before submission. A rapid double
click generated one request while the button displayed a disabled `Saving…` state.
That intended NGN 100 payment produced one authoritative payment, one balance change
and one receipt. A second NGN 120 request was committed by the backend while its
response was deliberately withheld from the browser. The UI displayed its existing
failure/retry guidance; retrying from the same form reused the same idempotency key,
returned the existing payment and produced no second financial effect. The total
balance reduction was NGN 220 for the two deliberately distinct payments, the receipt
endpoint returned HTTP 200, and no browser runtime error occurred. All temporary
payments were removed from the isolated fixture after verification.

**Slow-network usability gate: CLOSED.** No P0/P1 payment defect was found.

Vercel CLI identified the current `commercial-transformation` preview as Ready and the
configured production deployment and aliases as Ready. The production public site
loaded over HTTPS; the branch preview is protected by Vercel authentication. No
repository or process environment supplied an already authorized deployed school test
account, so application login and protected frontend-to-Railway calls were not
attempted. No production record, configuration, billing state or provider was changed.

**AUTHENTICATED DEPLOYED SMOKE TEST BLOCKED — AUTHORIZED TEST CREDENTIALS REQUIRED.**
**Deployment-compatible/authenticated deployment gate: PARTIALLY CLOSED.** The Basic
commercial foundation remains release-open solely for that authenticated deployed
workflow. The deferred P2 PDF calendar glyph remains unchanged. Batch 6 was not started.

### Controlled Basic production release preparation — 2026-09-26

The validated application candidate is `e85564b` on `commercial-transformation`.
Railway production currently runs `production-readiness-check` at `a35c67e`; the
canonical Vercel production project `school-portal` runs `3d0bfd`. Both are ancestors
of the candidate. The Railway release range is 10 commits; the canonical frontend is
40 commits behind because a newer duplicate Vercel project was deployed separately.

The release contains the validated billing/invoice and payment reconciliation work,
Basic account and parent operations, academic setup, configurable assessment/grading,
score review/publication protections, attendance/fee hardening, responsive workflows,
commercial simulation and release evidence. No unrelated runtime dependency or
deployment-file change appears in the Railway-to-candidate diff.

Production's applied migration baseline was read inside the running Railway service:
`fees.0008`, `gradebook.0002` and `tenants.0004`. The five release migrations are:

- `tenants.0005`: subscription-plan choice metadata; non-destructive.
- `fees.0009`: plan choice metadata plus idempotent Enterprise offer seed.
- `fees.0010`: new immutable term-invoice table, indexes and constraints.
- `fees.0011`: nullable invoice-verification fields and guarded payment constraints.
- `gradebook.0003`: new scoring-policy table plus score component/review columns.

Forward operations do not drop tables/columns or rewrite historical business values.
Existing payment rows satisfy the new constraints because invoice links default null.
Risk is moderate rather than zero: table alterations and constraint creation take
brief locks, and an application-only rollback after `gradebook.0003` is unsafe for old
score writes. A full backend rollback must therefore restore the verified pre-release
database snapshot; reverse migrations must not be used casually.

Production uses environment-supplied PostgreSQL, production Django settings and
Railway-private Redis. Required secret categories are present, explicit hosts/origins
are configured, migrations are enabled, database reset is disabled and Paystack is in
test mode. The persistent Postgres volume is present; customer-data population was not
inspected. Existing backup/schedule status must be verified in Railway before release.

The canonical production origin is `school-portal-gamma-two.vercel.app`, matching
Railway CORS/CSRF configuration. Its currently deployed API rewrite still uses a
placeholder backend hostname, a P1 production defect. The candidate's
`frontend/vercel.json` correctly targets `backend-web-production-cf61.up.railway.app`.
Production must be deployed through the root-linked `school-portal` Vercel project;
the duplicate project named `frontend` is not the canonical release target.

Before deployment, create and lock a timestamped Railway Postgres volume backup named
for the candidate, record the migration baseline, and take an encrypted off-repository
custom-format `pg_dump`. Verify the dump with `pg_restore --list` and a restore into a
separate database before treating it as rollback-ready. Record the backup timestamp,
checksum, restore result and operator-approved retention; never store it in Git.

Authorized release sequence: verify the backup; fast-forward
`production-readiness-check` to the final candidate; monitor Railway build, deployment
checks and five migrations; require HTTP 200 from `/health/`; deploy from repository
root to the linked canonical `school-portal` Vercel project; verify the production API
rewrite; then create a clearly synthetic Basic school and unique administrator through
the existing platform-owner onboarding workflow. Use no real people or transactions.
Run login, refresh, dashboard, students, staff, academics/results and fees as read-only
smoke checks, inspect protected request status/CORS/HTTPS/runtime behavior, and observe
Railway/Vercel logs for at least 15 minutes.

Rollback triggers are migration/startup failure, unhealthy backend, broken canonical
frontend integration, authentication/CORS failure, tenant-context error or unexpected
500s. Frontend-only failure restores Vercel deployment `dpl_Ghu5es4JaCJ9yLKcw5Yz748pJsfi`.
Backend or migration failure restores the locked database backup and Railway commit
`a35c67e` as one coordinated rollback. No production deployment, backup, migration,
configuration change or synthetic tenant creation was performed during preparation.

**PRODUCTION RELEASE PREPARATION COMPLETE — OPERATOR AUTHORIZATION REQUIRED.**
The authenticated deployment gate and Basic release milestone remain open.

### Production Checkpoint A: backup and restore drill — 2026-09-26

The preserved candidate is `5d001c0` on the remote `commercial-transformation`
branch. Railway production remained on application `a35c67e`, using
`config.settings.production` and PostgreSQL 18.6. The backup-time migration heads
were `tenants.0004`, `fees.0008` and `gradebook.0002`. Aggregate source counts were
captured at `2026-09-26T12:13:38Z` without reading customer identifiers.

Railway's production Postgres volume was confirmed ready. PITR is disabled and no
existing volume backups were listed. Both the current Postgres backup command and the
documented volume-backup API rejected creation as unauthorized; a platform snapshot
was therefore not created. This was a P1 release blocker under the original
Checkpoint A policy.

A closure attempt at `2026-09-26T12:33:11Z` confirmed that the active Railway session
is authenticated, belongs to the correct workspace and project, has workspace `ADMIN`
role, is not restricted by pending 2FA and uses the paid Hobby plan. The production
Postgres service and ready 5 GB volume were identified unambiguously, but Railway again
returned `Not Authorized` for the documented snapshot mutation and the verified backup
list remained empty. This rules out a stale login, wrong account, wrong project and
Free-plan limitation; Railway must grant or explain the remaining platform permission.

An independent PostgreSQL custom-format dump was created at
`2026-09-26T12:14:16Z` in a private backup directory outside the repository. The dump
is 308,068 bytes, its SHA-256 is
`f793fe1a1c520bd53a8d1f2050a2e86f693792ed99d5cd71c029400e9a7dd1e7`, and
`pg_restore --list` passed with 719 catalog entries and all representative tables.
The dump and checksum sidecar remain outside Git.

The dump restored without warnings into a newly initialized PostgreSQL 18.6 cluster
bound only to localhost and a clearly named temporary database. Expected tenant,
account, enrollment, fees, gradebook and attendance tables existed. Restored aggregate
counts exactly matched the backup-time counts: zero schools, zero students, zero staff,
zero payments, zero score entries and zero attendance records, plus one platform user.
All restored foreign keys were validated. Django connected to the restored database,
inspected migration state and repeated the matching ORM aggregate reads.

The restored and final production migration checks both left `tenants.0005`,
`fees.0009`, `fees.0010`, `fees.0011` and `gradebook.0003` unapplied. No migration,
restore, application deployment, configuration change or application/business-data
mutation occurred in production. The temporary restore cluster was stopped; its data
directory remains in the private backup area pending operator cleanup.

The operator accepts the verified custom-format logical backup and successful isolated
restore as sufficient recovery evidence for the initial Basic production release.
This release-specific exception does not make the Railway snapshot successful and does
not waive backup requirements for future releases. The existing dump remains available,
its recorded SHA-256 still matches, it is outside Git, production remains on `a35c67e`
with zero schools, and the candidate migrations remain unapplied.

**OPERATOR RISK ACCEPTANCE: APPROVED FOR INITIAL BASIC PRODUCTION RELEASE.** Before
meaningful school/customer data accumulates, resolve Railway snapshot authorization and
establish recurring backups, secure retention, restore drills, and explicit recovery
point/time expectations. Future database-changing releases require a fresh recoverable
backup appropriate to the data risk; automated/platform backup must not be indefinitely
waived once real school data exists.

**Logical backup, integrity, isolated restore and Django-read verification: PASSED.**
**RAILWAY PLATFORM SNAPSHOT: UNAVAILABLE — ACCEPTED OPERATIONAL FOLLOW-UP.**
**P2 OPERATIONAL FOLLOW-UP — RAILWAY PLATFORM SNAPSHOT UNAVAILABLE.**
**CHECKPOINT A — BACKUP & RESTORE: PASSED WITH DOCUMENTED PLATFORM-SNAPSHOT EXCEPTION.**
**PRODUCTION RECOVERY PROCEDURE: VERIFIED VIA LOGICAL BACKUP AND ISOLATED RESTORE.**

### Production Checkpoint B: controlled backend deployment — 2026-09-26

Checkpoint A was confirmed before release. Railway project `soothing-insight`, its
`production` environment, canonical `backend-web` service and PostgreSQL 18.6 service
were identified before any change. Production was healthy on `a35c67e`, had zero
schools and migration heads `tenants.0004`, `fees.0008` and `gradebook.0002`.
Production settings were active with `DEBUG=False`, PostgreSQL configured, reset on
deploy disabled, required secret categories present and Paystack in test mode.

Branch HEAD `9b34dfc` was deployed; its runtime backend/frontend tree is identical to
validated candidate `5d001c0` because the later commits contain recovery documentation
only. The read-only Django plan contained exactly the expected non-destructive
`tenants.0005`, `fees.0009`, `fees.0010`, `fees.0011` and `gradebook.0003` operations,
with no migration drift. Railway deployment
`4e3aff2a-a1e3-4f7e-9b05-8585558720ec` completed successfully.

The existing entrypoint passed deployment/system checks and applied all five migrations
successfully before Gunicorn 26.2.0 started. Post-release migration heads are
`tenants.0005`, `fees.0011` and `gradebook.0003`; Django reports no planned migration
operations. System metadata contains exactly one enabled Basic offer at NGN 800, one
Premium offer at NGN 1,500 and one Enterprise offer at NGN 2,500, with no duplicates.

Two HTTPS `/health/` requests separated by eight seconds returned HTTP 200 with HSTS,
content-type protection and no redirect. The platform profile endpoint returned 401
without credentials, while tenant routes without tenant context remained unavailable.
Bounded deployment logs contained no migration error, startup crash, database error,
repeated 500, missing dependency/settings error or worker requirement blocking Basic.

Authorized schema and system-metadata mutation occurred through the approved migrations.
No production school/customer record, payment or academic record was created or changed.
Rollback was not required, and no P0/P1 issue remains from Checkpoint B.

**CHECKPOINT B — CONTROLLED BACKEND DEPLOYMENT: PASSED.**

### Production Checkpoint C: canonical frontend deployment — 2026-09-26

Checkpoint B remained healthy before deployment: Railway `/health/` returned HTTPS
HTTP 200 and the migration heads remained `tenants.0005`, `fees.0011` and
`gradebook.0003`. The canonical Vercel account/team was `emio24` / `EMIO's projects`,
project `school-portal`, repository root directory `frontend`, output directory
`build`, and production alias `school-portal-gamma-two.vercel.app`. The previous
canonical deployment was `dpl_Ghu5es4JaCJ9yLKcw5Yz748pJsfi`; the separate Vercel
project named `frontend` was not used.

The candidate `frontend/vercel.json` rewrites `/api/*` to the canonical Railway
backend. The production `REACT_APP_API_URL` also points there; Railway's CORS, CSRF and
frontend origin settings include the canonical Vercel origin. A clean `npm ci` and
optimized production build passed with no compile error. The locally built JavaScript
was 315.52 kB gzip. Legacy npm deprecation and audit notices did not block the build.

Repository HEAD `5024d72` was deployed through the root-linked canonical project;
its frontend runtime content is identical to validated candidate `5d001c0`.
Vercel deployment `dpl_Vzy7JCHTEsLXPKPUuZJnL9XF5dCD` reached Ready and acquired
the canonical production alias. The production build passed. HTTPS requests for `/`,
`/features`, `/pricing`, `/demo`, `/contact` and `/login` returned HTTP 200 with the
Paideia HTML. The previous placeholder backend target is absent from the deployed
JavaScript, while the canonical Railway target is present.

The production Vercel `/api/school-lookup/` path returned Django JSON, and
`/api/platform/me/` returned Django's expected JSON 401 without credentials. This
proves the live Vercel API rewrite reaches Railway while preserving authorization.
The remote bundle contained no Paystack secret or private-key pattern. The frontend
and API targets use HTTPS. Headless Chrome rendered live-fetched production assets for
the landing page, school access form and platform login at 1440x900, 768x1024 and
390x844; headings and controls appeared, with no horizontal overflow or JavaScript
page errors. Direct browser network navigation timed out in the local test environment,
so production bytes were fetched over HTTPS and supplied to the browser for the layout
check; the live origin and API proxy were separately checked over HTTPS. `/login` on
the platform domain showed the expected school-not-found state because no school
tenant exists; `/access` and `/platform/login` remained usable.

After deployment Railway `/health/` still returned HTTP 200, the production school
count remained zero, and bounded backend logs contained no relevant 500, CORS, CSRF,
host or proxy error. No business data was created or changed. Frontend rollback was not
required and no P0/P1 issue remained from Checkpoint C.

**CHECKPOINT C — CANONICAL FRONTEND DEPLOYMENT: PASSED.**

### Production Checkpoint D2: operator-assisted authenticated smoke — 2026-09-26

The earlier Checkpoint D stopped because this agent environment's headless browsers
could not navigate the canonical Vercel site. D2 used a human operator's normal
browser for the real production journey and Railway for bounded backend checks.
Checkpoints A, B and C remained passed. Before creation, Railway `/health/` and the
canonical Vercel origin returned HTTP 200; PostgreSQL was 18.6, migration heads were
`tenants.0005`, `fees.0011` and `gradebook.0003`, Paystack mode was `test`, and
school, student and payment counts were zero.

One internal, non-customer `Paideia Production Test School` tenant (slug
`paideia-production-test`) and one school administrator were created through the
public registration endpoint. The existing owner school-management update and
approval views were then invoked from the Railway application environment under
the existing owner identity. The school was marked in platform notes as synthetic,
approved on Basic, and given no subscription end date. Public registration does
not set a first-password-change requirement for this account path. The temporary
credential was stored using Windows user-bound encryption outside the repository;
no credential or token is recorded here.

Before operator login, the canonical `/api/school-lookup/` resolved the synthetic
school, `/api/school/me/` returned its identity with the correct tenant header,
and nonexistent or missing tenant context returned 404. Unauthenticated `/api/auth/me/`
returned 401. The operator reported PASS for production load, school resolution,
one invalid-password rejection, valid login, correct tenant identity, dashboard,
students, staff, academics, attendance, fees, results/gradebook, refresh/session
persistence, mobile navigation, throttled navigation and logout. The operator saw
no error message or unrelated school data and created no operational records.

Bounded Railway logs covering the operator window showed login responses of 401
and 200, authenticated identity and protected-route 200 responses, and no 5xx,
traceback, CORS, CSRF or host-error marker. A separate transient school-admin JWT,
created inside Railway and never output, reached the canonical Vercel API rewrite:
`/api/auth/me/` and `/api/students/` returned 200 with the correct school identity;
`/api/platform/me/` returned 403; an invalid tenant returned 404. An internal
authorization check also gave the school administrator 200 for identity, students
and staff, 403 for platform-owner access, and 404 for invalid or missing tenant
context. One production tenant cannot prove cross-real-tenant isolation; existing
pre-production isolation tests remain supporting evidence.

Final aggregate checks found one synthetic school and one school administrator,
zero active students, staff profiles, parents/links, academic structures,
attendance, scores, results, fee schedules/payments, payment orders/exceptions and
term invoices. No payment or revenue was created; Paystack remained in test mode.
The platform school summary counts every active school without a synthetic
exclusion. Therefore the existing owner suspension action disabled the synthetic
tenant after the smoke: total schools = 1, active schools = 0, and public lookup
no longer resolves it. It is retained for future controlled smoke tests and must
not be interpreted as a customer or paying school. The total-school summary still
includes this disabled internal row; commercial reporting must exclude it.

The backend remained healthy after suspension. No P0/P1 finding remains. P2
operational follow-ups are: Railway platform/automated backup capability remains
unresolved and must be addressed before meaningful pilot/customer data accumulates;
production/release branch protection remains to be configured; and commercial
school-count reporting should explicitly exclude the disabled synthetic row.

Basic production baseline at 2026-09-26 22:06 UTC: source repository HEAD before
this documentation commit `5d67ee6ac8867925b2da78e2c1dc019d3fa35717`;
validated runtime candidate `5d001c0206706448752d6db2ed63f4abde793c59`;
Railway deployment `4e3aff2a-a1e3-4f7e-9b05-8585558720ec` running SHA
`9b34dfca8321963777f9c546f2fb2f0179cb64ee`; canonical Vercel deployment
`dpl_Vzy7JCHTEsLXPKPUuZJnL9XF5dCD` Ready, with Checkpoint C source evidence
`5024d72416253505f5350a7f09ee5d1cd4561ec7`; PostgreSQL 18.6; migration
heads `tenants.0005`, `fees.0011`, `gradebook.0003`; synthetic tenant retained but
disabled. The frontend runtime matches the validated candidate.

**CHECKPOINT D2 — OPERATOR-ASSISTED AUTHENTICATED PRODUCTION SMOKE: PASSED.**
**BASIC PRODUCTION BASELINE: ESTABLISHED.**

### Batch 6 reliability and recovery map — 2026-09-26

**BASIC PRODUCTION BASELINE COMMIT: 053a62ab6c738b5e501253df6c60d8c7b46015e3.**
This baseline was pushed to `origin/commercial-transformation` before Batch 6 edits;
the Batch 6 commit `3ea355c47f147a35a94bd1d1b21c2a6f2a6ca35d` was pushed
before Batch 7 and has not been deployed. The repository's release
deployment branch is `production-readiness-check`; permanent release-branch
protection remains an operator/governance decision (P2).

| Workflow | Baseline finding | Batch 6 treatment |
| --- | --- | --- |
| Score draft and submit | Backend draft persistence and assignment checks existed; failed save could leave the UI uncertain and navigation could discard edits. | Preserve edits, show save state, guard unsaved navigation, and make repeated lifecycle transitions return the current state without duplicate audit. |
| Result approval, publication and reopening | State checks existed, but a retry after a lost response could create a contradictory error or duplicate reopen audit. | Reconcile uncertain responses against the sheet and make already completed transitions idempotent after authorization. |
| Attendance | Session submit upserts were idempotent; a lost response gave no authoritative answer. | Read back the register after an uncertain save or lock; keep local marks when confirmation fails. |
| Manual payment | Server idempotency key already prevented duplicate credit; the UI could generate a new intent after an uncertain response. | Preserve the exact payment payload and key for retry. |
| Account/access and parent links | Authorization and tenant scope existed; identical retries could emit duplicate audit events. | Skip unchanged account edits and duplicate parent-link events. |
| Backup/restore | One logical dump, checksum, isolated restore and Django reads were proven; recurring/platform backups are unverified. | Clarify owner, proposed retention, manual fallback and incident steps in the recovery runbook. |

Local SQLite tests provide functional and bounded-query evidence only. They do not
establish PostgreSQL or production latency. No migration, dependency, new worker or
new production backup schedule was added in this batch.

### Batch 7 migration and onboarding — 2026-09-26

Batch 6 was preserved at `origin/commercial-transformation` before Batch 7 work.
Production continues on the validated Basic baseline. The existing student and
staff import endpoints remain available; the new school-admin Migration Centre
guides current-state CSV migration in this order: classes/arms, subjects, students,
teachers, parents, parent-child links and current-term teacher assignments.

The centre offers UTF-8 CSV templates and controlled, reviewable header mappings.
Only supported fields can map; system fields, roles and password columns are
rejected. Validation reads the entire file and current school records without
writing operational data. It reports CREATE, REUSE and REJECT per row, with field
reasons and ignored-column warnings. Import reads and validates the file again,
locks the school, commits valid rows in per-row savepoints, and records aggregate
counts in the existing platform audit stream. Identical retries reuse existing
records without overwriting them or adding an all-reuse audit event.

Migrated students have a school-scoped source reference (new additive migration
`enrollment.0006`) separate from their generated Paideia admission number. Parent
links use that source reference or an existing Paideia admission number. Teachers
and parents use school-checked email and phone identity; assignments use teacher
email, class level/arm, subject code and the current term. Parent contact fields
on students never grant parent portal access. Teacher accounts use existing
generated staff IDs and forced first password change; parent accounts use the
existing phone-login workflow. Imports cannot assign platform roles.

The readiness endpoint now includes active students alongside its existing
school, academic and assignment checks; the centre refreshes it after import.
Opening balances remain deferred: FeeSchedule represents current fee amounts and
FeePayment represents actual payments and receipts. Neither safely represents
an audited brought-forward debt without a new finance domain decision.

Files are request-scoped, limited to 2 MB/2,000 rows, never saved as customer
uploads by application code, and not logged. Rejected rows can be downloaded
locally for correction with formula-safe CSV cells. Tests exercise school-admin
permissions, cross-school references, protected columns, dry run, partial errors,
repeat imports, relationships and account state. A 400-student, 40-teacher,
40-parent, 20-arm, 15-subject, 20-assignment simulation completed validation,
import and student retry in 15.86 seconds on local SQLite. That timing says
nothing about PostgreSQL or production throughput. Historical records, automated
column transformation and opening balances remain deferred.

### Batch 8 mobile and resilience foundation — 2026-09-27

Batch 7 `5b2d56ce66a1d0f7e2e9cabfc7181643ff23f9ca` was pushed to
`origin/commercial-transformation` before this batch. The validated Basic
production baseline remains unchanged. No backend schema, dependency, worker,
production data or deployment was changed.

The existing authenticated shell already had a 1024px drawer, focus trap,
Escape handling and sign-out link. Batch 8 adds a shared browser connectivity
notice and a bounded read-failure classifier. Browser online state is only a
signal; request failures still drive page errors. Reconnection never resubmits
writes. Score drafts, attendance, result transitions and manual payments retain
their Batch 6 reconciliation/idempotency flows. Student/staff/fee directories
use labeled rows on phones; the gradebook keeps sticky identity columns and
internal scrolling; attendance controls have larger touch targets. The parent
dashboard clears a previous child's data during a switch and ignores a late
response for the child no longer selected. Fee balances are hidden while a new
page loads or a read fails, so an old amount is not presented as current.

No new persistent data cache was added. Existing cached school theme/branding
is relatively stable public metadata and is refreshed by ThemeProvider;
authorization remains server-driven. Student records, scores, attendance,
result publication, fee balances, payment state, permissions and account state
must remain authoritative from the server. The manifest and Paideia icons
already provide install metadata; registration of a nonexistent service worker
was removed. There is no offline read store, queued write or background sync.

Future offline work requires a per-tenant/per-user data classification, explicit
session/logout cleanup, conflict/version checks against server state, and a
decision on device encryption. Score and attendance conflicts need domain
resolution; financial writes must not be casually queued. Shared-device safety
currently relies on in-memory page state and protected-route authorization;
no Batch 8 operational data is persisted in the browser.

Local Chrome CSS fixture checks at 360×800, 390×844, 768×1024 and 1440×900
found no whole-page horizontal overflow for representative shell, directory,
gradebook, attendance and parent markup. The gradebook scrolls within its own
container. A separate local mock API served the built application for
authenticated Chrome smoke journeys: admin students, staff, migration and fees;
teacher score and attendance saves; parent child switching, results and fees;
and student dashboard, results, attendance and fees. Teacher saves, admin
search and parent child switching passed under 400 ms latency with 90 KB/s
download and 45 KB/s upload limits. The browser
showed offline and recovery notices after a brief connection interruption;
after sign-out and Back, the protected student row was not visible. These are
local mock journeys, not production network measurements. Component tests cover
delayed child switching, reconnect messaging and Batch 6 write behavior.
Production build
gzip sizes: JS 320.03 kB, CSS 43.91 kB; these are local build artifacts, not
transferred-byte or production timing measurements.

### Batch 9 portal designs — 2026-09-27

Batch 8 commit `0b942553ce0980bf8ae8467d92ff948cd67ea029` was pushed to
`origin/commercial-transformation` before this batch. The validated Basic
production baseline remains unchanged. No migration, dependency, worker,
production data, or deployment change is required.

One React component tree uses the existing school `theme_config` JSON. The
`layout` field names a validated design preset; the registry supplies suggested
palette, type and structural family. Semantic CSS tokens control shared
navigation, cards, density and radius. School colours override the suggested
palette when edited, while contrast-derived foregrounds and semantic status
colours remain separate. The five existing shell structures are reused; new
presets change composition and spacing within them. No school-specific code is
forked. Login uses the same preset ID; results, receipts and PDFs remain
separate document designs.

| Design | Structure | Distinct treatment |
| --- | --- | --- |
| Paideia Classic | Sidebar | Formal type, divided cards |
| Modern Academy | Masthead | Airy cards and wide spacing |
| Executive | Right rail | Management-first, two-column actions |
| Minimal | Narrow rail | Flat surfaces, reduced ornament |
| Scholar | Sidebar | Academic hierarchy, result-oriented cards |
| Horizon | Masthead | Soft cards and welcoming spacing |
| Prestige | Framed top navigation | Centre-aligned identity, elegant type |
| Compact Pro | Narrow rail | Dense tables and smaller cards |
| Campus | Masthead | Broad operational sections |
| Nova | Narrow rail | Split rail and bold action hierarchy |

Schools with no saved layout receive Paideia Classic. Saved `studio` and
`heritage` IDs remain valid and render through their previous structures;
unknown IDs fall back to Classic in the frontend. Owners retain the platform
appearance editor and plan controls. School administrators have a tenant-scoped
appearance editor at `/admin/appearance`, with a local preview before Save.
Its API only accepts validated theme fields for `request.tenant`; it cannot
change plans or another school. Meaningful saves record actor, school, changed
field names and old/new preset; repeat saves create no duplicate event.
School name, motto and logo remain managed through School setup and the
existing validated logo upload. Public branding is limited to the existing
public serializer. No raw CSS or JavaScript is accepted.

The shared Batch 8 mobile drawer, connectivity notice and read-failure handling
remain shared across designs. Document templates and full offline operation
remain separate product capabilities.

The isolated tenants suite passed 53/53, including the new tenant, validation,
legacy and idempotent-audit checks. Targeted React suites passed 19/19.
The first broader React run passed 294/299 tests; five failures appeared in
`BackendContracts`, `StudentDocuments` and `RouteCoverage`. A local Chrome mock-API matrix
passed 40/40 checks across all ten presets for desktop dashboard and student
directory, mobile dashboard and mobile login. Five deeper phone/tablet checks
passed for attendance, gradebook, fees, parent and student dashboards across
representative structural families. These are local smoke results, not
production measurements. Django check and migration consistency passed.
Production build gzip sizes are JS 321.63 kB (+1.60 kB) and CSS 44.94 kB
(+1.03 kB) against Batch 8. Fine-grained document/report styling remains
separate from portal appearance.

### Batch 9 frontend gate closure

The same five named failures reproduced on the isolated Batch 8 worktree
(`0b942553`) and Batch 9 (`7588d711`), each at 19/24 in the three focused
test files. None was introduced or worsened by Batch 9. The staff test
incorrectly rejected `new_email`, a supported backend serializer field. Two
teacher tests expected the old student-list score source, fixed score columns
and teacher publishing; the current school-configured `/sheet/` contract saves
`component_scores` and teachers submit for administrator review. The student
retry test expected the message predating Batch 8's network classifier.
The route inventory counted four components rendered inside routed pages as
missing routes; the corrected test verifies their routed parents and JSX use.

Only those stale test expectations were corrected. The three focused files
then passed 24/24. The full frontend suite passed 300/300 tests across 42
suites. No Batch 9 product regression or P0/P1 finding was identified. The
temporary baseline worktree was removed; Batch 9's previously passing build,
backend, browser and security evidence remains applicable. Production was not
changed.

## Post-Batch-9 master roadmap reconciliation — 2026-09-27

**Boundary.** Development `commercial-transformation` at `849068c` contains
Batches 6–9; production remains on the validated Basic baseline. That commercial
baseline is not final Basic. This is a plan only; none of the batches below is
implemented or deployed by this section.

**North star.** One connected school operating system: School Configuration →
People → Academics → Timetable → Teaching → Curriculum → Attendance → Assessment
→ Results → Finance → Communication → Parent/Student Experience → Management
Intelligence. Priorities: academic depth, operational visibility, reliability
and Nigerian-school fit. Authoritative, tenant-scoped records must support
metrics and cross-domain connections.

**Current boundary.** Plans, active-student billing snapshots, automatic 100+
discount, immutable subscription invoices, Paystack verification and idempotent
settlement exist. Basic has people, academics, configurable assessment/grading,
gradebook review/publication, attendance, manual fees/receipts, parent/student
portals, guided setup, Migration Centre, mobile/resilience foundations, ten
designs and appearance controls. Recurring timetable slots and conflict checks
exist; dated lesson delivery and curriculum tracking do not. Manual email/SMS
notification tools are currently Basic entitlements, with provider charges;
portal announcements and event automation are incomplete. CBT, analytics,
transcript and school-fee Paystack code exists but does not establish final
Premium commercial readiness. Enterprise inherits current Premium features
without multi-campus operations. Batch 6 proved one backup/isolated restore, not
recurring production backups.

**Final Basic.** Keep the existing core and add dated teaching delivery tied to
timetable slots, term/week/topic curriculum progress, principal operational
queues, controlled manual/portal communication, auditable student invoices and
opening balances, configurable report sections and core management reports.
Basic must support a normal daily school workflow without an always-on worker.
Do not silently remove its existing email/SMS entitlement: any split between
core communication and Premium automation needs a backward-compatible,
commercially approved decision.

**Premium.** Extend Basic with production-validated CBT, advanced results and
promotion, online school-fee payments, communication automation, and explainable
cross-domain analytics/intervention. Advanced migration/bulk operations are
proposed here, with tier placement to validate commercially. Assistive AI may
draft materials or explain source-linked trends only after privacy, evaluation
and cost gates; it must not set grades, attendance, payments, discipline,
permissions or reconciliation. Priority support is an operating policy.

**Enterprise.** Model school group → campus → campus operations before central
roles, approvals, executive reporting, bounded custom configuration and
integrations. Preserve tenant/campus isolation. Bespoke development and
dedicated resources are separately scoped and priced.

**Finance direction.** Fee structure → student invoice/ledger → payment →
balance → receipt → reconciliation → reporting. Batch 7 deferred opening-balance
migration because FeeSchedule/FeePayment cannot represent brought-forward debt
with auditable origin. Batch 14 designs and tests that domain before importing
balances. Discounts, scholarships, instalments and credits need provenance and
adjustment rules. This is school-fee finance, not general accounting. Paideia
subscription invoices remain a separate immutable billing domain, retaining
the existing rolling-month extension.

**Communication and infrastructure.** Basic provides controlled manual/portal
communication and retains currently entitled manual email/SMS tools. Premium
adds event triggers, delivery/retry tracking and provider cost controls. SMS
credits and payment fees remain separately charged. Enterprise may add approved
institutional audiences/integrations. Basic runs on Django/PostgreSQL with
synchronous core workflows. Premium may use shared Redis/Celery/Beat where
justified; Enterprise also defaults to shared hosting. No worker per school.
WhatsApp/push require demand, API and cost validation before implementation.

**Sequence decision: Path A.** Finish final Basic operating workflows before
Premium expansion. Existing timetable, academics, attendance and fees supply
the dependencies. Teaching and curriculum then produce principal metrics and
communication events. CBT-first development would leave that daily operating
chain incomplete. Each batch must include tenant isolation, RBAC, audit,
historical integrity and safe retry tests; final hardening verifies rather than
introduces security.

| Batch | Name | Tier | Main outcome | Depends on | Risk |
| --- | --- | --- | --- | --- | --- |
| 10 | Teaching Operations | Basic | Record dated scheduled/delivered/missed lessons | Timetable/assignments | Medium |
| 11 | Curriculum Progress | Basic | Term/week/topic plans tied to lesson evidence | 10 | Medium |
| 12 | Principal Operations | Basic | Actionable daily queues from authoritative data | 10–11, attendance/fees/results | Medium |
| 13 | Communication Centre | Basic | Manual/portal audiences and history | 12, notifications | Medium |
| 14 | Student Finance Ledger | Basic | Auditable invoices, adjustments and opening balances | Fees/Migration Centre | High |
| 15 | Controlled Reports and Basic Validation | Basic | Configured documents, reports and full-term simulation | 10–14 | Medium |
| 16 | Assessment & Learning Delivery | Basic + Premium | Basic term CBT; Premium question bank, configurable CBT, paper exams and assignments | 11, 15, existing CBT | High |
| 17 | Academic Standards, Curriculum Intelligence & Continuity | Shared | Curriculum provenance/versioning, school standards, lesson plans/resources, approval, continuity and factual academic oversight | 11–12, 16 | High |
| 18 | Online School-Fee Payments | Premium | Safe payment allocation/reconciliation | 14, existing settlement | High |
| 19 | Communication Automation | Premium | Event triggers, delivery/retry and cost controls | 13, 18 | Medium |
| 20 | Advanced Migration and Assistive Tools | Premium | Historical/bulk import and a bounded assistive pilot | 14, 17, privacy gates | High |
| 21 | Institutional Hierarchy | Enterprise | Group/campus model, roles and approvals | Basic/Premium data contracts | High |
| 22 | Enterprise Reporting and Integrations | Enterprise | Executive reports and scoped external interfaces | 21 | High |
| 23 | Integrated Release Hardening | Shared | Recovery, security, performance and deployment evidence | 10–22 | High |

**Boundaries and completion signals.** Batch 10 proves an auditable dated lesson
outcome, including cancellation/substitution, teacher/admin permission and
cross-tenant tests; no timetable generator. Batch 11 proves planned, covered
and remaining topics from lesson evidence; no AI curriculum. Batch 12 proves
source-linked principal attendance, teaching, result and finance queues with
correct date boundaries; no decorative counts. Batch 13 proves audience
selection, manual announcement and history; no event automation. Batch 14 proves
invoice/payment/adjustment reconciliation and audited opening-balance import;
no general ledger. Batch 15 proves configurable PDF sections, broadsheets,
core reports and a realistic full-term Basic journey; no drag-and-drop designer.
These Basic batches use existing infrastructure unless measurement demands more.

Batch 16 proves Basic term CBT and Premium assessment delivery, including paper
exams, online assignments, gradebook handoff and tenant-safe concurrency.
Batch 17 establishes curriculum provenance, approved school standards, lesson
plans/resources and year-to-year academic continuity; it uses factual evidence
without invasive teacher monitoring. Batch 18
proves fee allocation and repeated webhook/reconcile safety; no new provider.
Batch 19 proves event delivery, retry/audit and spend limits; no free unlimited
SMS. Batch 20 proves validated historical import and, only if gates pass, one
opt-in reviewed assistive use case; no automated decisions or obligation to ship
AI. Premium jobs use shared workers only when needed. Batch 21 proves campus
and central-role isolation with approvals; no campus code forks. Batch 22
proves scoped integration contracts and cross-campus totals without leakage;
no speculative vendor adapters. Batch 23 proves recurring restore, browser/PDF,
slow-network, concurrency and rollback gates; it does not defer security fixes.

**Milestones.** Final Basic Operational Baseline follows Batch 15 after a normal
school term including finance and principal workflows passes. Premium Commercial
Baseline follows Batch 20 after CBT, automation, payments and intelligence are
commercially validated; optional AI is not a gate. Enterprise Baseline follows
Batch 22 after campus isolation/central workflows pass. Paideia 1.0 Candidate
follows Batch 23 after cross-tier integration and release/recovery evidence.
Every milestone needs a separate deployment decision.

**P2/deferred.** Recurring/platform production backups and retention; release
branch protection; disabled synthetic school in commercial school totals;
opening-balance model (14); historical import and broader format/column
transformation (20); full offline only after tenant/user cache privacy design;
production mobile/network measurements; Batch 9 report/document polish (15).
Do not report these as closed or elevate harmless P2 work without evidence.

**Recommended next batch: Batch 10 — Teaching Operations.** Use the existing
timetable and assignments to record dated lesson outcomes and exceptions, which
become trustworthy inputs for curriculum and principal views. This roadmap
does not begin implementation.

### Batch 10 teaching operations — development evidence, 2026-09-27

Roadmap commit `85513a9` was pushed to `origin/commercial-transformation`
before implementation. Production remains on its prior Basic baseline.
Existing Period/TimetableEntry, Term/Holiday, tenant middleware, school RBAC,
platform audit and mobile/design primitives were reused.

**Occurrence strategy:** lazy. A day view derives unresolved lessons from
weekday, term bounds, non-break periods and configured holidays. It creates no
future or fabricated historical outcomes. An explicit save creates one
`LessonRecord` per school + original timetable slot ID + date. The unique
database constraint, transactional row lock, revision check and unique-race
read-back protect duplicate, stale and simultaneous saves. Repeating the same
outcome is a no-op and emits no extra audit event.

**Historical representation:** the record retains the original slot ID and
nullable slot link, term name, class/subject identifiers and names, period
name/times, scheduled teacher identifier/name, actual teacher/name, outcome,
note, original actor/timestamp, update timestamp and revision. Recorded history
survives timetable edits, slot deletion, subject renaming and teacher account
deactivation. A deleted term still leaves the snapshot readable by date.
Unresolved dates are derived from the *current* timetable; historical
unrecorded schedules are not versioned and must not be treated as proof of
missed teaching.

**Outcomes and roles:** no row means “Outcome not recorded.” Delivered and
missed require an affirmative teacher/admin save. School admins alone record
cancellation and same-school active-teacher substitution. The originally
scheduled teacher and actual substitute remain distinguishable. Assigned
teachers may save their own current-day scheduled lesson; admins may inspect
and correct school records. Parents, students, platform owners, unrelated
teachers, foreign tenant references and inactive substitute teachers cannot
write. Meaningful record/correction transitions use PlatformEvent; unchanged
retries do not. Holiday dates cannot acquire a new outcome from a recurring
slot. Past recorded outcomes remain readable when the current term changes.

**Portal and resilience:** teacher and admin pages use shared cards and tokens.
Teachers choose a date, see their own schedule and record an outcome on a
phone. Admins filter date/class/teacher/subject/outcome and control substitutes.
An uncertain save reads the dated authoritative list before claiming success;
an unconfirmed save leaves an explicit review/retry message. No Redis, worker
or Beat is required.

**Validation:** targeted timetable tests: 12 on SQLite (11 pass, one
PostgreSQL-only skip); 12/12 on an isolated local PostgreSQL cluster, including
two simultaneous first saves and exactly one audit event. The affected backend
suite passed 109 tests with one PostgreSQL-only skip. One versus 21 daily
slots both used five SQL queries under SQLite and local PostgreSQL. Targeted
frontend tests passed 5/5; affected frontend suites passed 31/31. Local Chrome
mock-API journeys confirmed delivery/refresh at 390×844 and 1440×900, no
whole-page overflow in Classic, Minimal, Compact Pro and Nova at 360×800 and
1440×900, and read-back confirmation after an aborted 390px save response.
An admin browser journey at 768×1024 recorded missed, corrected to cancelled,
then assigned a substitute without whole-page overflow. These are local
mock/browser measurements, not production timings. Django
check and migration consistency passed; the additive migration was applied
by the SQLite and PostgreSQL test runners. The final frontend production
build passed (gzip JS 323.73 kB, CSS 45.44 kB).

**Deferred:** a complete school-calendar engine, immutable versions of
unrecorded historical schedules, server pagination for unusually large daily
admin lists, richer substitution scheduling and full offline operation.
Curriculum Progress → Batch 11. Principal Operations → Batch 12. Neither is
implemented by Batch 10.

### Batch 11 curriculum management and holiday-aware progress — development evidence, 2026-09-27

Batch 10 `eaca847` was pushed and verified at `origin/commercial-transformation`
before Batch 11. Production remains on the prior Basic baseline. The new
`curriculum` app adds one school-owned plan per term, class level and subject;
all arms of a level reuse its plan. Weeks (1–52) hold ordered topics and
individually identified, ordered objectives. Plans are term-bound, so changing
the current term does not alter old schemes. No legacy curriculum or coverage
is inferred or backfilled.

**Evidence and progress.** A `TopicCoverage` row links one topic to one
authoritative `LessonRecord`; the unique lesson/topic constraint permits both
multiple topics in a lesson and the same topic across lessons. Coverage is
allowed only for delivered or substituted outcomes and matching school, term,
class level and subject. Missing coverage means not started; active partial
evidence means partial; any active covered evidence means covered. The summary
counts distinct unarchived topics by actual class arm, with per-week counts
and dated lesson evidence. Archived topics with lesson history remain in the
historical counts; untouched archived topics are excluded. Planned week never implies delivery or overdue
status. Teachers can correct or deactivate coverage using revisions; identical
retries add no row or audit event. Lesson and topic row locks serialize saves,
and a covered lesson cannot be corrected to missed/cancelled until active
coverage is removed. Plans cannot change a topic's content, order or
objectives once any historical coverage exists; the topic may be archived,
but its record and evidence remain. Objective-level delivery is deferred.

**Calendar and access.** Existing Session → Term → Holiday CRUD and the
administrator's Academic Calendar UI were reused. Holiday API validation now
checks full ranges including partial edits, term boundaries and foreign terms.
Started holidays cannot be edited/deleted; meaningful create/change/delete
actions are audited. Batch 10 already excludes configured holiday dates from
unresolved scheduled lessons; it creates no holiday or missed `LessonRecord`.
The scheme displays configured breaks as calendar context, never as delivery
or automatic completion. No ahead/behind label is inferred without a reliable
teaching-day expectation. Admins manage schemes and see per-arm progress;
teachers see only assigned schemes and can record coverage for lessons they
actually delivered (including authorized substitution). Parents, students,
platform owners, foreign tenants, subjects, terms and classes cannot mutate
school curriculum through these routes.

**Portal and reliability.** The admin Scheme of Work page creates and edits
topics/objectives by week, links to Holiday setup and shows source-linked
progress. My Scheme lists a teacher's active assignments; My Teaching shows
read-only planned topics before delivery and quick partial/covered controls
after delivery. All use shared design tokens and mobile cards. An uncertain
coverage response reads the authoritative lesson record before claiming a
save; no offline mutation queue, Redis, Celery or new dependency is added.

**Adjacent P1 corrections found by affected validation.** PostgreSQL rejected
gradebook result submission because `FOR UPDATE` also targeted a nullable
joined policy; the lock now scopes to ScoreEntry. The existing public
scratch-card checker could consume a valid PIN with no published score. It
now checks result availability before consumption and assembles the result
inside the same transaction. Scratch-card architecture, generation, pricing,
navigation and UI remain intact. Batch 15 must still commercially validate
result-access entitlement, empty states, revocation, batch lifecycle, mobile
branding, rate limits, audits, term history and end-to-end school simulation.

**Validation.** Targeted PostgreSQL curriculum/calendar tests: 19/19; one
focused result-card test: 1/1; affected PostgreSQL backend suite: 50/50,
including coverage races, outcome/coverage serialization, holiday exclusion,
tenant attacks and the Basic result-submit journey. Curriculum plan read:
13 SQL queries with one topic and with 21 topics on isolated local PostgreSQL.
Targeted frontend curriculum tests: 6/6; affected frontend suites: 28/28.
Local Chrome mock-API checks exercised teacher scheme at 360×800 (Scholar),
lesson coverage save/readback at 390×844 (Classic), admin topic creation at
768×1024 (Compact Pro), and admin read at 1440×900 (Nova), without whole-page
overflow. A prior phone check confirmed read-back after an aborted write.
These are local mock/browser observations, not production measurements.
Django check, migration consistency and the production frontend build passed;
the additive `curriculum.0001_initial` migration applied in PostgreSQL tests.

**Deferred:** objective-level delivery, curriculum copying/import, richer
calendar-to-week mapping, reliable ahead/behind indicators, broader offline
editing and parent/student curriculum views. Principal Operations → Batch 12.

### Batch 12 principal operations — development evidence, 2026-09-27

Batch 11 `d56d6cada00bd6b9eaca98bd739ea8da8d63e9ab` was pushed and verified
at `origin/commercial-transformation` before this work. Production was not
changed. The Basic school-admin dashboard now reads `/api/principal/` directly
from tenant-scoped source records. The endpoint accepts a bounded section,
selected date and school term; it has no writes, cached snapshot table, worker
or new migration. Teachers, students, parents, platform owners and foreign
school users cannot read it. Premium analytics remains separately gated.

The old dashboard's enrollment count was partial; its cached average, pass
rate, fee collection percentage, leaderboard and low-attendance alert were
not reliable principal operations facts. The dashboard now shows active
enrollment and teaching staff, finalized attendance marks and class coverage,
dated lesson outcomes, explicit lesson-linked curriculum topic coverage,
score-entry review states and recorded payments against configured term fee
schedules. Every actionable group links to its existing source workflow.
An unfinalized attendance register is excluded because starting one creates
default-present marks before review. Missing finalized class registers are
shown separately from absence. Unrecorded lesson outcomes remain distinct
from missed lessons. Holidays and weekends suppress expected teaching and
attendance. For dates older than seven days, teaching shows only stored
outcomes because recurring timetable history is not versioned.

Finance reports only payments recorded against selected-term schedules, not
receivables or cash ledger totals. Curriculum reports covered, partial and
not-started topics, never ahead/behind. Section-level errors can be retried;
late responses from an older selection are ignored. The admin attendance,
teaching, curriculum and results pages accept dashboard filter links.

On isolated local PostgreSQL, the six read sections used 5/9/7/6/3/6 SQL
queries (snapshot/attendance/teaching/curriculum/results/finance). The same
counts held after adding five students, two class arms and twenty topics to
the fixture; the combined read cost was 36 queries across six independent
HTTP sections. Batch 10's dated lesson projection also held at five queries
with one and 21 slots. Targeted principal tests: 7/7; affected backend tests:
66/66. Targeted dashboard/teaching frontend tests: 8/8; affected
curriculum/result review tests: 8/8; full page inventory: 59/59. Django
check, migration consistency and optimized frontend build
passed. Local Chrome mock-API views at 360×800 Scholar, 390×844 Classic,
768×1024 Compact Pro, 1440×900 Nova and Executive rendered with no whole-page
horizontal overflow. Mock navigation verified Teaching Operations and Scheme
of Work links; a 503 finance section recovered through Retry. These are local
browser and query observations, not production performance claims.
An additional local Chrome check followed the filtered result review link and
changed the school date to a mocked configured holiday; attendance and teaching
both displayed the holiday state and no false alarms. The source workflow
journey and retry used only mock API data and a local static build.

Deferred: historical timetable versioning, ahead/behind curriculum inference,
advanced analytics and AI. Communication Centre remains Batch 13; the
Student Finance Ledger remains Batch 14; scratch-card/PIN commercial
hardening remains Batch 15.

### Batch 13 Basic Communication Centre — development evidence, 2026-09-27

Batch 12 `a8654497065f19dbc295c2877b24b4984bbdbde3` was pushed and
verified at `origin/commercial-transformation` before Batch 13. Production
was unchanged. The existing `notifications` app has templates, per-student
email/SMS logs, an idempotent batch and a Celery outbox. Basic already
includes the `notifications` entitlement. That legacy sender targets guardian
contact text rather than linked parent accounts and needs a worker for live
external delivery; it has no SMS credit ledger. Its capture mode records
pending logs without external delivery. It remains available as the separate
Email and SMS tool, with its existing behavior and entitlement unchanged.

The new `/api/communications/` path reuses the notifications app and the
Basic entitlement. School admins alone may preview, publish and inspect
history. No distinct Principal role exists in the current RBAC; the
Principal Command Centre still uses school-admin permission. Teachers may
read their own notices but cannot broadcast. Parents and students read only
their own recipient rows. An inactive account cannot use this path. The
server ignores a client-supplied school ID and always scopes by request
tenant. Foreign class, parent, staff and student IDs are rejected.

Audience queries support all linked parents, class parents, selected linked
parents, active staff, class teachers, selected staff, active students,
class students and selected students. Parents come only from verified
`ParentStudentLink` rows for active students. Guardian contact text grants no
access. A multi-child parent has one recipient row per notice. Class-parent
preview reports active students without a linked active parent; empty
audiences cannot publish. Recipient search returns at most 50 account names
without contact details; the notice limit is 2,000 unique accounts.
Class teachers are drawn from current-term subject assignments and current
class/assigned-class links, excluding historical subject assignments.

Publishing stores a `Communication` and one `CommunicationRecipient` per
unique account in a single PostgreSQL transaction. Title, body, sender name,
audience label, intended count and recipient membership are historical
snapshots; a changed class, removed parent link or deactivated sender does
not rewrite them. Sent notices have no edit/delete API. Content is plain
text rendered by React, without trusted HTML. A platform audit event records
the sender, tenant, audience and count, never message content or contacts.
Portal status `available_in_portal` means the notice is in an account inbox;
`read` means that account opened it, not that the person understood it.
History and inbox are paginated, with read counts and no recipient contact
list. Publishing needs a tenant-scoped idempotency key and has a per-sender
120/hour local-cache throttle. Reusing a key with the same payload returns
the existing notice, even after audience membership changes; changing the
payload returns 409. The browser retains its key after an uncertain response
and asks the sender to check history before retrying. There is no retry
worker or automatic trigger.

The Centre offers portal delivery only. Existing email and SMS infrastructure
cannot safely be joined to this linked-account audience in the bounded Basic
batch: it uses per-student guardian text, a worker-backed outbox, and has no
SMS credit accounting or per-recipient provider-confirmed delivery link.
Therefore the Centre makes no email/SMS delivery claim or chargeable send;
the existing external tool is linked and remains separate. Email provider
acceptance and SMS provider acceptance in that tool are not proof of human
delivery. A later controlled integration must resolve identities, credits,
provider semantics and scale before exposing combined channels.

The new admin composer previews counts, confirms publication and shows
history/detail. Parent, teacher, student and admin notices share one inbox
component, the existing navigation and design tokens. The browser stores no
message draft or send queue. Basic works with Django and PostgreSQL alone.
The frontend requires no new dependency. Advanced automation and delivery
workers remain Batch 19/Premium; WhatsApp is deferred. Student Finance Ledger
remains Batch 14 and scratch-card/result-access hardening remains Batch 15.

Validation used isolated local PostgreSQL. Seven focused backend tests cover
audience selection, deduplication, tenant/role attacks, snapshot integrity,
idempotency, read state, pagination, plain-text storage and a 101-parent
audience. In that fixture, preview used at most 12 SQL queries and publish
at most 18, independent of recipient count; inbox/history each used at most
eight queries in the smaller fixture. Targeted frontend tests cover preview,
zero recipients, publish, uncertain response reuse and inbox reading. The
affected frontend suite included an outdated Batch 12 App heading assertion;
its expectation was aligned to the existing Principal Command Centre title.
Local Chrome mock-API journeys covered admin publish/history and parent
inbox/read at 360×800 Scholar, 390×844 Classic, 768×1024 Compact Pro,
1440×900 Nova and Executive with no page-level horizontal overflow. These
are local observations, not production performance or delivery measurements.

## Batch 14 — Student finance ledger

Batch 13 commit `3d9554ccf942b72860d32aa1c7fdfec69d1d73a1` was pushed
and verified on `origin/commercial-transformation` before this batch. The
production baseline was not changed. Earlier finance used mutable FeeSchedule
amounts minus FeePayment sums to infer balances. FeePayment and receipt PDFs
were genuine payment records, but the actual historical student obligation
could not be reconstructed after fee edits or for a school migrating old debt.
The old debtor list inherited that ambiguity. Manual payment already had a
school-row lock and deterministic receipt number for retry keys; those remain.

StudentFinanceAccount records whether a student account is active or needs
legacy opening review. It stores no balance. StudentLedgerEntry is the
authoritative dated history: charge, opening, payment, discount, scholarship
and adjustment entries are signed. Positive entries add debt; negative entries
reduce it. `sum(signed_amount)` is the account balance; positive balance is
outstanding and negative balance is an explicit credit. All amounts are NGN
Decimal(14,2), with exact cent validation and no binary float calculation in
the backend. Zero is displayed only after an actual entry (including a
verified zero opening). A missing account or unreconciled legacy account is
unknown, never zero. Entries preserve actor name, timestamp, effective date,
reason/reference where applicable, tenant and academic context. `FeePayment`
continues to own receipts; one ledger payment links to one real FeePayment.

Admins synchronously generate charges from current FeeSchedule rows for
active students. Each charge snapshots amount, class, due date and source
schedule. The school-row lock and unique student/schedule charge constraint
make repeats safe. Later edits to FeeSchedule do not change existing charges.
An opening balance represents verified net debt or credit at a cutover date,
including old obligations; it is not a payment or a current-term charge.
Accounts with old receipts start in `legacy_review`, without fabricated
charges. Generation skips them until opening review; after opening, it skips
fee structures for terms starting on or before the opening's effective date.
Payments against those old structures reduce the opening balance without
creating a duplicate charge. A school must choose a cutover date that
separates old obligations from new charges. Pre-cutover receipts remain
downloadable but their original obligation provenance is unknowable from
today's FeeSchedule rows.

The guided Migration Centre now accepts one verified opening balance per
student source reference or admission number, with nonnegative amount,
debt/credit direction, effective date, reason and source reference. It uses
the existing CSV mapping, preview, rejected-row and confirmation flow. A
matching rerun is reused; a different opening is rejected for manual review.
Historical payment transactions are not imported or invented. Schools may
also record a single opening balance from the admin student-account page.

Manual and existing verified Paystack school-fee payments enter the same
ledger service in the transaction that creates the FeePayment. Manual retry
keys still resolve to the same receipt; conflicting details return 409.
The existing Paystack checkout reads frozen charge remainder where present
and requires school review for ambiguous legacy balances or unapplied account
credit; it does not silently charge a changed fee structure or ignore credit.
School-row locks serialize charge generation, payments and adjustments under
PostgreSQL. A payment is explicitly tied to one fee structure. It allocates
to that student's frozen charge up to the unpaid amount; any excess, when
explicitly permitted, remains account credit. Partial and repeat payments
are supported without a formal instalment schedule. Discount and scholarship
entries require a generated charge and reason. Signed adjustments require
an actor and reason and remain visible as corrections; they never edit an
old entry. School audit events record action and signed amount without
credentials. No delete or edit endpoint exists for entries or allocations.
Student fee cards report payment allocations separately from discounts and
scholarships so an award is never labelled as a cash payment.

Admin accounts, debtor totals, parent dashboard, student fee view and the
Principal finance summary now read ledger states. Debtors are active students
with a positive known whole-account balance. Credits and verified zeros are
excluded; unknown accounts are counted separately. Debtor totals are
calculated before pagination. Class, session, term, student search and
minimum-outstanding filters are available on the debtor API; term/session
select accounts with activity in that period while balances remain whole
account. Parent access requires an explicit linked child; students see only
their own account. The shared history view shows running balance and real
receipt links. Admin mutation remains school-admin only because the current
RBAC has no separate Principal role. The Principal view shows known ledger
outstanding/debtors and flags partial finance state when accounts are
unverified; its period's recorded-payment count still uses FeePayment.

The Basic ledger runs synchronously on Django Web and PostgreSQL. It needs
no Celery Worker, Celery Beat, Redis or new always-running Railway service.
Formal instalment schedules, historical payment import and advanced account
exports are deferred. Paystack school-fee expansion may reuse the settlement
hook in Batch 18; automated debtor/payment communications remain Batch 19.
Controlled reports and scratch-card/result access hardening remain Batch 15.

Validation used isolated local PostgreSQL for money and race tests, and the
existing isolated browser sandbox for UI journeys. The 500-student commercial
simulation's finance list returned 50 rows in seven SQL queries and 85 ms
locally; this is local evidence, not a production service-level claim.
PostgreSQL races covered repeat charge generation, repeat adjustment keys,
same-key payment retries and two payments competing for one charge. Browser
checks covered admin charge generation, account history, discount, partial
payment, authenticated receipt PDF, linked-parent and own-student history at
1440x900, 768x1024 and 390x844 with no page-level horizontal overflow.
The affected PostgreSQL suite initially found the old seven-query finance
gate exceeded; the account summaries were consolidated and the 500-student
gate then passed. The full affected suite was not repeated after that
isolated performance correction because its guided-migration load test took
over four hours; focused PostgreSQL finance, query and concurrency tests
were rerun. No production deployment or data mutation occurred.

## Batch 15 — controlled reports and Basic validation

Batch 14 commit `b5cd970d218af44f41e653bf3d275fcafc58730b` was pushed
unchanged and its full SHA verified at `origin/commercial-transformation`
before Batch 15 edits. Production remains unchanged. Existing `ScoreEntry`,
assessment policies, grade bands, published results, remarks, finalized
attendance, school branding, PDFs and optional scratch cards remain the
sources of academic and identity data. Report configuration changes only
presentation: Classic Academic, Modern or Compact; title; display of comments,
attendance, position, skills and known next-term date; and a bounded watermark.
Assessment columns use the configured score components. Signatures remain
printed signing lines because there is no approved signature-image workflow.

The first publication of a term captures the school's bounded presentation
settings and branding in `PublishedReportStyle`. Later configuration changes
affect previews and future terms, not an already published term. The data
migration captures the best-known current branding for terms published before
this release and assigns their original Classic appearance; their exact
historical branding cannot be reconstructed if it was changed earlier.
Official student and parent results require all existing score rows for that
student and term to be published; partial reopening hides the official slip,
class ZIP and public card response until republished. Broadsheets additionally
require current position totals. School admins
can preview unpublished entries with a conspicuous preview label. Historical
report class and attendance totals follow the score's class arm, not a
student's later class assignment or sessions from other classes. Only
explicitly recorded, finalized attendance contributes; a missing register
remains unknown. Position
computation rejects incomplete publication. The printable result fallback
still contains real subjects, configured component scores, totals and grades
when native PDF rendering is unavailable.

Scratch-card serials and PINs use cryptographic randomness; PINs remain
hashed. Public checking has generic failure responses, the existing 10/min
anonymous throttle, term-bound published-result checks and an atomic
single-use update. Revoked cards remain visible to administrators with actor
and timestamp but cannot be used. Batch summaries distinguish generated,
used, unused and revoked cards. A card is optional; authenticated Basic
student and linked-parent result access does not require one. Card generation
retains its existing Premium entitlement; Basic does not gain that feature.
Unbound cards
retain the existing current-term behavior; bound cards fetch their own
historical term. Basic does not acquire Premium CBT or online fee-payment
entitlements.

Validation uses isolated local PostgreSQL and the existing disposable browser
sandbox, never production data. The 500-active-student simulation connects
teaching evidence, curriculum coverage, a portal notice, published result,
student finance, Principal summary and a valid optional scratch card. The
Principal Command Centre currently uses school-admin authorization; there is
no distinct Principal role. Browser validation covered report configuration,
authorized preview, own published student result and admin navigation at
1440x900, 768x1024 and 390x844 without page-level horizontal overflow. The
ten existing portal designs remain one shared component tree with distinct
structural treatments. The Basic request/database path needs no Worker,
Beat, Redis or extra always-running Railway service; production settings
accept a local-memory cache when `REDIS_URL` is absent. Distributed public
throttle coordination is weaker without Redis and should be revisited only
if traffic or abuse warrants a shared cache.
Optional Celery calls execute eagerly without Redis so a memory broker cannot
silently discard queued work; normal Basic operations do not invoke them.

The frontend regression passed 47 suites and 320 tests, and its production
build compiled successfully. The isolated browser sandbox passed admin report
configuration, student result access and navigation at the three sizes above.
The local 500-student performance sample measured report configuration at two
queries and one student report at 16 queries; the latter is constant for one
student's report data, not a bulk PDF throughput claim. The broad affected
PostgreSQL regression passed 326 of 326 tests with no failures, closing Batch
14's earlier 195/196 evidence gap. Its 500-student sample measured debtor
listing at seven queries, Principal snapshot at five and teacher daily slots
at five for both one and 21 slots. These are isolated local observations, not
production latency guarantees. The guided migration simulation processed
400 students, 40 teachers, 40 parents, 20 arms and 15 subjects in isolated
SQLite; the commercial simulation ran on PostgreSQL. Django system and
migration checks passed. No P0/P1 finding remains from this batch's affected
release review.

FINAL BASIC OPERATIONAL BASELINE: ESTABLISHED locally. This decision covers
the connected Basic workflows and the web/PostgreSQL cost profile; it does
not deploy code or change production. Deferred work remains bounded:
unrestricted report design, scheduled bulk PDF generation, formal instalment schedules,
historical payment import, a separate Principal role, CBT commercial
hardening, advanced academic intelligence, online school-fee expansion,
automated communications, assistive AI and multi-campus workflows.

### Batch 16 assessment and learning delivery — development evidence, 2026-09-29

The existing CBT models, attempt timing, option randomization and gradebook
policy remain the foundation. New schema adds a question source (`term` or
reusable `bank`), optional academic term and curriculum topic, per-question
marks, exam component mapping, immutable attempt class/score facts, school
subject assessment mode, paper snapshot, assignment/submission records, and
gradebook component source metadata. Migrations are additive; historical
question rows default to the reusable bank source. Basic authors only in the
current term and selects those questions manually. The previous term's Basic
questions are excluded from new authoring and selection; completed attempts
retain their question snapshots. Premium bank questions persist across terms
and may reference the existing scheme topic. No official curriculum is
fabricated. That topic relationship is an extension point for Batch 17's
academic-standard continuity work, which is not implemented in Batch 16.

A school administrator selects CBT or paper for a subject, class level and
term. Published CBT and submitted paper artifacts prevent a conflicting mode
change in that period. CBT remains server timed. Objective and short-answer
questions have validated answer keys and positive marks; theory questions are
reserved for human-marked paper/assignment work. Attempts snapshot questions,
class and raw earned/maximum marks. A completed CBT may fill only an explicit
configured gradebook component. The service normalizes raw marks to that
component's maximum using decimal half-up rounding: 42/50 into a 30-mark
component becomes 25.20. In the tested 100-mark policy, other components of
8, 7 and 44 produce 84.20 total. A student row lock, component-source record,
and draft/published guards make repeated writes idempotent and reject a
different source or manual overwrite.

Premium paper blueprints select objective/theory counts from exact active
scheme topics for the selected term, subject and class. The server reports a
topic-specific shortage, snapshots the chosen bank questions, permits a
same-topic draft replacement, and locks the submitted/approved version.
Only a school administrator approves; unapproved PDFs carry a DRAFT label.
The school name, eligible Cloudinary logo, session, term, subject, class,
duration, instructions, sections, question marks, pagination and separate
authorized marking copy are rendered by the existing WeasyPrint dependency.
External PDF image URLs are restricted to the configured Cloudinary cloud.

Premium online assignments share the same tenant, term, class, subject and
optional scheme-topic relationships. Students see only published/closed work
for their current class and never receive answer keys. Responses are saved
server-side before submission, with explicit failure and retry states in the
browser. Deadline and repeat-submit rules are server enforced. Objective work
can be scored from a snapshot; teachers release marks and feedback. Practice
work never changes the gradebook. Graded work reserves one configured
component for the class/subject/term and uses the same locked integration
service. No new queue, worker, dependency or external service is required.
Attachment uploads are deferred because this batch has no safe bounded
assignment-file storage contract; answers and feedback use text and existing
question images.

The access boundary uses school-scoped querysets, school/term/subject/class
validation, current teacher assignments, plan middleware and student-specific
submission views. Attempted CBT exams cannot be deleted; questions are
archived so historical answers remain intact. The regression suite covers
Basic/Premium entitlement, cross-school records, answer-key secrecy, class
visibility, paper shortage and draft label, assignment retries, gradebook
source conflicts and PostgreSQL simultaneous integration. Frontend route and
offline-save tests cover the added workspace. Browser validation uses only the
disposable QA schools; no production school or credential is used.
