# Payment exception operations

Phase 8 adds operational case tracking to existing Paystack PaymentOrders for
school fees and subscriptions. It does not execute refunds, change original
payments, adjust fee balances or extend/cancel subscriptions. Amounts are not
accepted by the case API. Partial/full refund rules and any later financial
adjustments remain **BUSINESS DECISION REQUIRED / LEGAL REVIEW REQUIRED** under
the [Phase 7 draft](PAYMENT_AND_REFUND_POLICY_DRAFT.md).

## Enter and inspect a case

- A school administrator may POST `/api/fees/exceptions/` with `reference`, `kind`
  and `reason`, using the existing school context. GET the collection or
  `/api/fees/exceptions/{id}/` to inspect its public case fields. No internal
  notes/history or provider refund confirmation references are exposed here.
- Platform owners use `/api/platform/payment-exceptions/` and the corresponding
  `/{id}/` detail endpoint. The existing Payments screen includes an exception
  panel for creation, filtering, inspection and review. Owners can report on
  behalf of schools, including suspended schools; normal school suspension still
  blocks tenant access. Case access is not restricted by the current plan tier.
- Students, parents, teachers and platform viewers cannot manage these endpoints.
  Users report issues to their school administrator through the agreed channel.
  No new public payment-request or student-search endpoint is introduced.
- Types: `refund`, `duplicate`, `incorrect`, `provider`, `manual`. A refund case
  requires an already successful local order as a technical prerequisite, not a
  determination of refund eligibility. Other cases can investigate pending,
  failed, abandoned (locally failed) or review payments.
- List filters: `status`, `kind`, exact payment `reference`; `next_before` provides
  the cursor for the next page via `before`. Detail includes payment reference,
  provider transaction ID, payer/student IDs, amount/currency, time, mode and
  fee allocations or subscription plan for owner investigation.

Supply only the operational reason and concise investigation notes. Never enter
card numbers, CVV, credentials, raw provider payloads or unrelated student data.

## Review and decisions

Owner PATCH requires `expected_status`, the desired `status`, and a nonempty
`admin_notes` entry. Optional `provider_ref` is accepted only when resolving a
refund after independently confirmed provider completion.

Refund lifecycle:

`requested -> under_review -> approved OR rejected`

`approved -> provider_pending -> resolved OR provider_failed`

`provider_failed -> provider_pending` records a manually arranged retry.

Other case types use `requested -> under_review -> resolved`. Investigation notes
may be recorded without changing a nonterminal state. Rejected and resolved cases
are final; the API has no deletion or history-rewrite endpoint.

Approval records the owner's decision and rationale only. It is not provider
authorization, proof of money movement, a refund entitlement or an automated
refund. Provider-pending/failed states are operator reports, not fabricated API
responses. Resolve a refund only after independent confirmation, recording its
provider refund reference and a note explaining the evidence and outcome. This
closes the case; original successful payment and receipt history remain intact.
No accounting reversal is implied. Any actual refund amount and subsequent
accounting treatment require a separately approved process; do not infer a refund
amount from the original order amount displayed for investigation.

## Duplicates and discrepancies

Matching amounts/payers/dates never automatically classify payments as duplicates.
Record a report against the original reference, put any related transaction
references in the investigation note and inspect the existing orders. A suspected
duplicate does not automatically create or approve a refund case.

Use existing owner payment verification/reconciliation to investigate local/provider
discrepancies. It validates Paystack results and reuses settlement; the exception
API itself never contacts Paystack. Verification failure or unavailability is not
proof of success, failure or refund. No background retry loop is added. Successful
orders retain existing reconciliation behavior; independently investigate claims
about completed refunds without rewriting successful settlement history.

## Audit and repeated submissions

Each payment/type has one durable case, enforced by a database unique constraint
and transaction locking. An identical create returns that case; a different
reason for the same payment/type returns a conflict so an administrator inspects
the existing case rather than creating duplicates. No second refund execution
can be triggered because this API has no execution function.

Updates lock the case, check the expected state and validate transitions. Identical
update retries do not append another audit event. The existing private PlatformEvent
store retains actor, timestamp, previous/resulting states and investigation notes;
the current note is a convenience view, not a replacement for history. Audit writes
and case changes are atomic. Application diagnostic logs receive no new payloads.

## Deployment and limits

Migration: `fees.0008_payment_exception` adds the case table/uniqueness constraint;
it does not rewrite PaymentOrder or FeePayment data. Production migration is a
separate controlled deployment action and is not applied in Phase 8.

Existing reconciliation, fee allocations and webhook idempotency are reused without
modification. Cash/bank-transfer FeePayment entries without a PaymentOrder are not
turned into synthetic Paystack orders by this workflow.

Actual provider execution is manual and requires explicit operational approval.
Automated refunds and real-money provider testing are **DEFERRED TO PAYSTACK LIVE
READINESS**. No LIVE switch, secrets change, financial transaction or Phase 9 work
is authorized by this runbook. Eligibility, partial/full refunds, deadlines, fees,
school-fee responsibility and disputes remain unresolved in the Phase 7 draft.
