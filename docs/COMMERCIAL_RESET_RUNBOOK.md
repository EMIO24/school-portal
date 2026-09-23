# One-time commercial reset — awaiting production approval

**RESET_DB_ON_DEPLOY MUST BE DISABLED IMMEDIATELY AFTER THE ONE-TIME RESET
AND BEFORE REAL CUSTOMER DATA IS INTRODUCED.** Leaving it enabled repeats
the destructive reset on every qualifying web-service startup, including restarts.
This document does not authorize or execute a reset.

## Preconditions

- Obtain separate approval for production promotion and the destructive reset.
- Confirm a current production backup exists, is accessible, and has a verified
  restore procedure (see `DISASTER_RECOVERY.md`). Confirm there is no real customer
  data to preserve; stop if any is found.
- Promote and deploy the bootstrap fix and pilot-seeder removal with reset disabled.
- Confirm `/health/`, marketing homepage and `/access` work before the reset.
- Keep Paystack in TEST mode. Existing deployment checks must permit test payments
  through `DEPLOYMENT_CHECK_ARGS=--allow-test-payments`; do not switch to LIVE.
- Confirm the intended database and web service, `RUN_MIGRATIONS=true`, and that
  both configured owner environment variables are present. Do not copy their values
  into logs or this document. Prevent concurrent web startups during the reset.

## Actual startup sequence and controlled operation

1. After explicit reset approval, enable `RESET_DB_ON_DEPLOY=true` only for the
   controlled web startup. Do not introduce customer data during this window.
2. Startup runs `deployment_check`, then `check --deploy --fail-level WARNING`.
   If either fails, it stops before the reset.
3. Startup runs `flush --noinput`: managed application table rows are removed and
   PostgreSQL sequences reset. Tables and migration history remain. Django restores
   content types and permissions; already-applied data migrations are not replayed.
4. Startup runs `migrate --noinput`, then `bootstrap_platform`. The bootstrap
   atomically creates missing Basic (NGN 800) and Premium (NGN 1,500) offers, enabled
   for three months. Existing offers are preserved, including disabled/customized
   offers. No free-plan offer is needed. The existing 100+ active-student 10% discount
   remains unchanged. Bootstrap failure stops startup before owner creation/Gunicorn.
5. Existing startup logic recreates the configured platform owner if absent, then
   starts Gunicorn. No synthetic school, user or payment records are seeded.
6. Verify successful migrations and the bootstrap completion message. Immediately
   disable/remove `RESET_DB_ON_DEPLOY` and restart/redeploy with reset disabled.
   If any stage fails, disable reset before retrying; investigate rather than
   repeatedly flushing. Confirm the restart does not log another reset.

## Verification before onboarding

- Verify no pending migrations and exactly one Basic and one Premium offer with
  the default amounts, three-month duration and enabled status after this reset.
- Verify the configured platform owner exists with superadmin access. Owner MFA
  and other application records were erased too; restore required owner access
  controls before operational use.
- Verify `/health/` is healthy, the marketing homepage works, and `/access` works.
- Confirm these slugs no longer resolve through school lookup/access:
  `cedarfield`, `bright-future`, `heritage-model`, `kingsway`, `paideia-demo`.
- Confirm in the database that no synthetic schools or users remain, not merely
  that those five slugs are absent. The configured platform owner is expected.
- Confirm reset is disabled before any real school onboarding. Cloudinary objects
  and Paystack provider records are not deleted by this reset; their old database
  references are removed. Do not delete external records as part of this procedure.

## First real school

Do not create it during preparation. Its entitlement is Premium with a negotiated
school-specific NGN 800 per active student per term. Public Premium stays NGN 1,500;
do not encode the negotiated price in global offers, create a "pilot" plan, or change
Premium features. School identity, administrator and population must be supplied
separately. Confirm the school-specific commercial arrangement before billing.
