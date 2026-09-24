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
