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
- Branding: five validated layouts and school identity exist; ten semantic-token
  presets and draft/publish appearance are later slices.
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
