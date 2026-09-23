# Payment and Refund Policy — draft

**LEGAL REVIEW REQUIRED.** This describes product behavior and open commercial
questions, not a final refund promise or legal advice.

## IMPLEMENTED PAYMENT BEHAVIOR

- Basic: ₦800 per active student per term. Premium: ₦1,500 per active student per
  term. At least 100 active students receive an automatic 10% subscription
  discount. The count is taken at checkout from active student profiles.
- The existing seeded offer covers three calendar months. Successful subscription
  settlement extends from the later of today and the current unexpired end date;
  it does not reactivate a suspended school. Confirm term/offer alignment in the
  school agreement. This is not a new annual or recurring-debit commitment.
- School administrators initiate subscription purchases through Paystack.
  Student school-fee payments are separate and use the school's configured
  Paystack subaccount. School fee schedules are school-managed, not the platform
  subscription price. This document establishes no extra fees.
- A browser return alone does not establish payment. Server verification and
  authenticated webhook handling validate provider results before settlement.
- Verified matching success settles the relevant order. Verified failed or
  abandoned transactions become locally failed without credit. Genuine pending
  transactions remain pending; verification outages do not imply failure.
- Amount/currency/customer/reference/mode mismatches and changed settlement
  conditions remain under review without credit. Owner reconciliation verifies
  against Paystack and reuses the existing settlement logic.
- Repeated processing of the same successful order does not create duplicate
  settlement, receipts or subscription extensions. Separate genuine charges still
  need investigation; idempotency is not a refund mechanism.
- Orders, provider references, fee payments and receipts support operational
  tracing. Keep the reference when raising a question; never send card details,
  passwords or provider secrets through an enquiry form.

## BUSINESS / LEGAL DECISION REQUIRED

Phase 8 now provides operational request/review/decision tracking, without
automatic provider execution or financial adjustments. See
[Payment exception operations](PAYMENT_EXCEPTION_OPERATIONS.md). This does not
finalize refund eligibility or change the unresolved policy questions below.

| Question | Decision required before publishing final terms |
| --- | --- |
| Subscription refunds | Eligibility, request/approval process and any legally required rights. |
| Mistaken payments | Validation evidence, responsible party and correction/refund handling. |
| Duplicate payments | Distinguish repeated callbacks from separate charges; decide resolution. |
| School-fee refunds | School versus platform responsibilities and Paystack handling authority. |
| Partial refunds | Eligibility, calculations and effect on fee balances/subscriptions. |
| Cancellation after payment | Service access, unused periods and financial consequences. |
| Disputes/chargebacks | Escalation, evidence, communications and applicable rights. |
| Billing details | Due dates, renewal communication, plan-change/proration rules and taxes. |

No automatic refund, blanket refusal, refund deadline or cancellation charge is
established. Obtain business approval and professional legal review before these
rules become final. Existing software notes suggesting owner review/refund do not
constitute an approved refund policy or an implemented automated refund workflow.

For school-fee questions start with the school administrator. For platform
subscription enquiries use the agreed school support channel, or the existing
`/contact` page leading to `/demo` until an official contact is confirmed.
The public form is a general enquiry mechanism, not a guaranteed dispute service.
