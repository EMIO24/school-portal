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

Next: invoice-linked checkout/reconciliation and customer-facing invoice screens/PDFs.
Existing paid periods and historical payments need an explicit compatibility policy;
do not invent historical term invoices or apply a second subscription extension.

After invoices: Basic workflows, theme system, Premium hardening, necessary
Enterprise foundations, full school simulation, then release freeze and full checks.
