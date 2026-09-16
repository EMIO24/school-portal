# Launch pricing assumptions - 15 September 2026

Configured launch offers: **Basic NGN 75,000 / 3 months**, **Premium NGN 150,000 / 3 months**. Editable by owners; current pending checkouts keep their original price. No auto-debit. Plan access is now enforced. Basic includes daily school operations; Premium adds CBT, advanced analytics, bulk imports, promotion and scratch cards. All five layouts are included on every plan. Confirm staffing capacity before promising additional priority support. See PLANS_AND_DESIGNS.md.

This is a starting operating budget, not a provider quote or a guarantee of profit. Use actual student counts, storage and traffic to review prices after the first billing cycle. Larger schools and exceptional migration/support work need a separate quote.

| Shared monthly cost | Planning allowance (NGN) |
| --- | ---: |
| App hosting, PostgreSQL, Redis/workers, backups and network usage | 100,000 |
| Cloudinary/media reserve while usage is small | 20,000 |
| Domain renewal reserve (30,000/year assumption) | 2,500 |
| Transactional email | 5,000 |
| Monitoring/security tools | 10,000 |
| Support, maintenance and onboarding labour | 100,000 |
| Subtotal | 237,500 |
| 20% contingency | 47,500 |
| Initial monthly target | 285,000 |

Railway Pro includes USD 20 of monthly resource usage; it is not an unlimited hosting/database package. Usage beyond included credits increases cost. [Railway pricing](https://railway.com/pricing).

Cloudinary has free and paid tiers; its pricing page lists a USD 99 tier. The initial media reserve assumes low usage, not that NGN 20,000 buys that tier. Using an illustrative **NGN 1,600/USD budget rate** (not a current exchange-rate quote), reserve about NGN 160,000/month when that upgrade is needed. Replacing the media allowance with 160,000 raises the contingency-inclusive target to **NGN 453,000/month**. [Cloudinary pricing](https://cloudinary.com/pricing).

Paystack's standard Nigerian local charge is 1.5% + NGN 100, capped at NGN 2,000. Basic therefore nets approximately NGN 73,775 per payment (NGN 24,591.67/month); Premium nets NGN 148,000 (NGN 49,333.33/month), before taxes, refunds and other costs. School fee processing charges come out of school settlement, independently of platform subscriptions. [Paystack pricing](https://paystack.com/pricing).

At the initial target, approximately **12 Basic schools or 6 Premium schools** cover the modeled monthly costs. At the paid-media target, approximately **19 Basic or 10 Premium schools** are needed. A mix of 10 Basic + 5 Premium produces about NGN 492,583/month after local gateway fees. Below break-even, budget startup capital or reduce costs; do not assume one school's subscription pays all shared expenses.

SMS is excluded from subscriptions: arrange prepaid provider credit or bill actual usage plus an agreed service margin. SMS cost depends on destination, network and message segments; price from the selected provider's current quote. This implementation does not yet enforce an SMS wallet or automate usage invoices. Restrict sending budgets operationally until metering exists.

These allowances do not establish actual supplier bills, tax obligations or a founder's salary. Track taxes/accounting, refunds/chargebacks, marketing, extraordinary support and replacement costs separately, then include them in the next price review. Prefer annual provider billing only after usage is predictable. Set provider spending alerts and review monthly database/storage/backups, media transformations/bandwidth, email and SMS usage. Never advertise unlimited storage or SMS at these prices.
