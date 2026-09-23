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

## Next slice: immutable term invoices

Add an invoice tied to school/session/term, active-student snapshot, rate, discount,
effective rate, amounts, issue/due dates, status, payment linkage and audit metadata.
Use immutable issued amounts, a uniqueness/idempotency policy and authorized
adjustments. Reuse the quote service and existing verified payment settlement.
Historical payments must not be silently converted into invented term invoices.
Add school/owner invoice views and tests for changed populations, tenant attacks,
duplicate generation and all 15 plan/count boundary combinations.

After invoices: Basic workflows, theme system, Premium hardening, necessary
Enterprise foundations, full school simulation, then release freeze and full checks.
