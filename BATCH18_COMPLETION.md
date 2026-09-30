# Batch 18 — Online School-Fee Payments and Migration Improvements

Status: **COMPLETE — REGRESSION CONFIRMED 2026-09-30**

Branch: `complete-version`

## Scope completed

Batch 18 completed the online school-fee payment flow and strengthened migration/onboarding import support.

### Online school-fee payments

- Server-authoritative fee allocation payloads.
- Partial and full fee payments.
- Frozen checkout amounts derived from Paideia financial truth.
- Idempotent checkout retries using `Idempotency-Key`.
- Safe handling of initialization timeouts and uncertain provider state.
- Strict tenant ownership validation at settlement.
- Strict stored allocation validation.
- Payment-order type routing protection.
- Legacy unlinked subscription compatibility preserved.
- Paystack school subaccount validation before checkout reopening and before settlement.
- Fail-closed behavior when the linked settlement account changes or disappears.
- Balance drift detection before crediting.
- Provider verification before success is accepted.
- Webhook signature validation plus provider re-verification.
- FeePayment creation followed by ledger posting and allocation.
- Immutable receipt history preserved.
- Parent/student payment return and re-authentication recovery.
- Platform reconciliation and checkout-reopen safety.

### Migration Centre

- CSV and XLSX support.
- Server-side workbook inspection.
- 2 MB / 2,000 row import limits.
- First worksheet only.
- Header mapping and suggested mappings.
- Protected identifiers blocked.
- CREATE / REUSE / REJECT behavior.
- Validation before import.
- Rejected rows retained for correction.
- Formula cells are not executed and mapped formula cells are rejected.
- Existing Migration Centre flow remains compatible with the hardened import path.

## Financial invariants

1. PostgreSQL and the Paideia ledger remain the financial source of truth.
2. Browser-supplied amounts are never authoritative.
3. Provider success alone does not create a financial credit.
4. A fee payment is credited only after provider, tenant, allocation, balance, and settlement-account validation.
5. Receipt/ledger drift fails closed.
6. A missing or changed Paystack school subaccount moves the order to review rather than crediting it.
7. Repeated verification is idempotent.
8. Repeated checkout requests with the same idempotency key cannot create duplicate financial intent.
9. Historical subscription orders created before invoice linkage remain supported only when they match the exact legacy subscription shape.
10. Invoice-backed subscription orders remain protected by invoice-specific database and settlement checks.

## Final regression results

### Backend

- Targeted Batch 18 finance gate: **62 / 62 passed**
- Full backend suite: **401 / 401 passed**

### Frontend

- Targeted payment/recovery suites: **21 / 21 passed**
- Full frontend suite: **49 / 49 suites passed**
- Full frontend tests: **335 / 335 passed**
- Snapshots: **0**
- Production frontend build: **successful**

## Completion decision

Batch 18 is complete.

No protected-branch merge or deployment is implied by this status. The completed work remains on `complete-version` until an explicit promotion/deployment decision is made.
