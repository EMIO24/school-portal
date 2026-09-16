# Paystack setup and testing

Payments now cover school fees and portal subscriptions. School fee money is routed to the school's Paystack subaccount, less Paystack charges. Subscription money goes to the platform Paystack account. No platform commission is deducted from school fees.

## Open the pages

- Platform owner: http://localhost:3001/superadmin/payments (sign in at /platform/login).
- School administrator: http://localhost:3001/admin/subscription?school=qa-school
- Student: http://localhost:3001/student/fees?school=qa-school
- Parents: open a linked child's fees from the parent dashboard.

Basic starts at NGN 75,000 and Premium at NGN 150,000 per **three calendar months**, not an academic term. Owners can edit the price, period and availability in Payments. Renewals require a new checkout; there is no automatic debit. Plan features are now enforced: Basic includes everyday school operations; Premium adds CBT, analytics, bulk imports, promotion and scratch cards. See PLANS_AND_DESIGNS.md. SMS is not included or automatically metered/billed by this change.

## Enable local TEST checkout

1. In the Paystack dashboard, switch to Test Mode and copy your **test secret key**.
2. Create the ignored local file `.testing/paystack.json` with this content, replacing the placeholder privately:

```json
{"secret_key": "sk_test_REPLACE_PRIVATELY"}
```

Never paste the key into chat or frontend files. The local integration server rejects live keys. Without this file, external payments stay disabled.

3. Restart the backend from the project folder:

```powershell
python scripts/integration.py serve
```

Stop the existing backend with Ctrl+C first if you launched it in a terminal. Frontend command:

```powershell
npm --prefix frontend run start:integration
```

4. In Paystack Test Mode, create a separate subaccount for each test school. Verify the beneficiary bank details in Paystack, then copy its `ACCT_...` code.
5. As platform owner, open **Payments**, select the school and connect its subaccount. Check the displayed beneficiary name and bank suffix. Test and live mappings are separate. The same subaccount cannot be assigned to two schools.
6. Sign in as the school administrator and select **Portal subscription**. Pay using the test options displayed by Paystack. School fee checkout additionally requires the school's connected subaccount.

Local test accounts are listed in `.testing/accounts.json`; owner credentials are in `.testing/platform-owner.json`. Do not share those files publicly.

## Checklist

- [ ] Owner can open Payments even with no selected school, and manage suspended schools' settlement settings.
- [ ] School admins, students, parents and read-only platform staff cannot manage platform payment settings.
- [ ] Subscription checkout shows the configured price. Successful verification changes the school's plan and paid-through date once.
- [ ] Paying does not activate a suspended or unapproved school.
- [ ] Student selects outstanding fees; checkout charges the remaining balance only.
- [ ] A school without a connected settlement account cannot start fee checkout.
- [ ] A linked parent can pay; an unrelated parent/student cannot view or pay another student's fees.
- [ ] Returning from Paystack shows payment status and PDF receipt downloads after verification. Refreshing does not create extra receipts.
- [ ] Failed/pending payment produces no fee credit. Keep its reference and use **Check again**; do not pay again until resolved.
- [ ] Owner's **Verify with Paystack** button reconciles a recent payment if the browser did not return.
- [ ] At phone width, forms fit the page, references wrap, and buttons remain usable.
- [ ] In a public test deployment, repeated signed webhooks produce only one receipt/renewal.

The browser redirect is not proof of payment: the backend checks Paystack's reference, amount, currency, customer email and test/live mode. Signed webhooks are also re-verified. Orders survive server restarts. Duplicate pending checkouts are blocked. If an initialization timeout leaves an unknown reference, the owner must reconcile it with Paystack before permitting another payment. There is no button that marks an unverified online payment successful.

## Public deployment activation

Set these **backend environment variables** in your hosting service (not React):

```text
PAYSTACK_SECRET_KEY=sk_live_REPLACE_PRIVATELY
PAYSTACK_MODE=live
FRONTEND_URL=https://your-portal-domain.example
```

Use test mode/test key on a staging deployment first. Run migrations on the intended deployment database:

```powershell
python backend/manage.py migrate
```

Use your deployment's normal DJANGO_SETTINGS_MODULE. Register this public HTTPS webhook URL in the matching Paystack dashboard mode:

```text
https://YOUR-BACKEND-DOMAIN/api/platform/paystack/webhook/
```

Paystack cannot reach localhost; local checkout returns can still verify payments. Reconnect every school's **live** subaccount before accepting school fees. Complete Paystack business activation and beneficiary checks in its dashboard. Never switch a production school into test mode to simulate paid subscriptions: use a separate staging database.

Review orders marked **review** before credit/refund decisions. A changed fee balance or subscription plan can require reconciliation. Refunds, disputes, automatic reminders, SMS wallets and recurring subscriptions are not automated by this release. Use the Paystack dashboard for refunds and record the reconciliation in platform activity/notes. Schedule independent database backups and retain payment records; see RECOVERY_GUIDE.md.

## Automated checks

```powershell
python backend/manage.py test fees tenants accounts --settings=config.settings.test
npm --prefix frontend test -- --watchAll=false --runInBand --runTestsByPath src/__tests__/pages/Payments.test.js
```

Tests mock Paystack and do not charge money. Real test-mode checkout and webhook delivery require your Paystack configuration.

Implementation references: [Paystack accepting payments](https://paystack.com/docs/payments/accept-payments/), [split payments](https://paystack.com/docs/payments/split-payments/), [webhooks](https://paystack.com/docs/payments/webhooks/).
