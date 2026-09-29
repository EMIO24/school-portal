# Batch 18 — Online School-Fee Payments

Status: **IN PROGRESS**

Batch 18 extends the Batch 14 student finance ledger rather than creating a second balance system.

## Operating-cost rule

Basic school-fee payment remains request-driven on the existing Django web service and PostgreSQL database.

This batch does **not** require:

- a Celery worker;
- Celery Beat;
- Redis;
- a new always-on service;
- polling for payment completion.

Paystack callbacks, explicit verification and signed webhooks remain the external-payment boundary.

## Slice 1 — ledger-backed partial online payments

The existing Paystack fee checkout already verified provider reference, amount, currency, mode and payer identity and posted successful payments to `FeePayment` plus the student ledger.

This slice tightens initiation:

1. Before an external checkout is created, Paideia freezes the selected fee obligation as a ledger charge.
2. Unverified legacy accounts remain blocked from online payment.
3. Existing account credit must be resolved before a new checkout.
4. Student/parent checkout may specify a positive partial amount for each selected fee, up to its frozen outstanding amount.
5. The previous `fee_schedule_ids` contract remains accepted and means "pay the full outstanding amount" for compatibility.
6. Settlement still rechecks every selected fee against the authoritative outstanding balance before posting any receipt or ledger credit.
7. Duplicate verification/webhook delivery remains idempotent.

The student/linked-parent fee screen now allows an amount per selected fee and shows the selected total before redirecting to Paystack.

## Excel migration support

The Migration Centre now accepts both:

- UTF-8 `.csv`
- Excel `.xlsx`

Both formats use the same domain rules, mapping, preview/validation and CREATE/REUSE/REJECT import workflow.

Excel constraints:

- maximum upload size remains 2 MB;
- maximum data rows remain 2,000;
- the first worksheet is used;
- protected/system columns remain rejected;
- formulas are never executed and mapped formula cells are rejected;
- imports remain school-admin and tenant scoped;
- rejected rows can still be downloaded as CSV for correction.

Excel parsing uses `openpyxl` only during an upload request. It adds no persistent runtime service.

## Regression coverage added

- partial Paystack payment posts only the requested verified amount to the finance ledger;
- partial checkout cannot exceed frozen outstanding balance;
- Excel inspect → validate → import works through Migration Centre;
- Excel formula content is rejected;
- frontend fee checkout uses the allocation/amount contract;
- frontend Migration Centre inspects `.xlsx` before validation.

## Still to complete in Batch 18

- payment-return UX and explicit reconciliation states;
- broader parent/student/admin payment-history and receipt journeys;
- payment exception/refund workflow review against ledger semantics;
- multi-fee partial-payment regression coverage;
- Paystack test-mode staging verification;
- full affected backend/frontend regression and production build.

Production branch is not changed by this work.
