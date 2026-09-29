# School Service Agreement — draft

**LEGAL REVIEW REQUIRED.** Working draft for discussion, not legal advice or a
professionally reviewed contract. Do not present it for signature as final until
the review checklist is completed. No jurisdiction or legal entity is assumed.

## Parties and service schedule

- Provider: [PAIDEIA LEGAL ENTITY], [AUTHORIZED REPRESENTATIVE].
- School: [SCHOOL LEGAL NAME], [AUTHORIZED SCHOOL REPRESENTATIVE].
- Effective date: [EFFECTIVE DATE].
- Selected plan: [BASIC OR PREMIUM]; school portal: [SCHOOL PORTAL NAME].
- Billing term: [TERM]; checkout active-student count: [COUNT].
- Approved support contact/channel: [TO BE CONFIRMED].

Paideia provides a customized digital school portal configured for the school.
The selected plan determines the available administration, academic, payment and
assessment tools. Record the agreed configuration and onboarding tasks in the
service schedule. No annual commitment, free trial or additional fee is created
by this draft.

## Subscription and payment responsibility

Basic is ₦800 per active student per term; Premium is ₦1,500 per active student per
term. At 100 or more active students, the checkout automatically applies a 10%
discount to the subscription total. The school supplies accurate enrollment/status
records and its authorized administrator arranges subscription payment. The
current checkout counts profiles marked active and records the quoted order.
The seeded subscription duration is three calendar months; settlement extends
from the later of today and an existing unexpired subscription end date. Align
the agreed billing term with the configured offer before contracting; do not
promise automatic alignment to every school's academic calendar.

Subscription purchases and student school-fee payments are separate. Verification,
reconciliation and refund decisions are described in
[Payment and Refund Policy Draft](PAYMENT_AND_REFUND_POLICY_DRAFT.md).
Mid-period plan changes require owner assistance under the existing checkout
rules. Due dates, proration, renewal notices, taxes and upgrade arrangements are
**BUSINESS / LEGAL DECISION REQUIRED**; this draft creates no new charge.

## Onboarding and accounts

The school identifies an authorized administrator, checks imported records and
parent links, supplies permitted branding assets and assigns appropriate roles.
Public school registration requires approval before access. Paideia configures
the agreed portal and operates the implemented access controls. Students can use
school-scoped name login with an admission number when needed; personal student
email is optional in the approved implementation. The production migration and
smoke test remain controlled deployment prerequisites.

## Operational data responsibilities

| Area | School responsibility | Paideia operational responsibility |
| --- | --- | --- |
| Student/staff records | Decide appropriate collection, accuracy and authorized access; optional demographics are not required for core functionality. | Apply implemented tenant, role and response-field controls. |
| Parent relationships | Verify who is legitimately linked to a child and correct inaccurate links. | Enforce explicit links for protected parent access. |
| Accounts and roles | Authorize users; review assignments and departed personnel; arrange deactivation. | Provide existing account/access management controls. |
| Passwords | Protect credentials, change initial passwords and report suspected compromise. | Use existing password hashing and authentication protections. |
| Uploads and content | Supply content the school is authorized to use; avoid confidential documents in public image facilities. | Operate configured storage and protected record access; image URLs are not a private document vault. |
| Incidents | Report suspected misuse through the agreed channel without sending passwords or sensitive records through a general enquiry form. | Triage through existing operational controls and recovery procedures. Notification obligations/timelines require legal review. |

These are operational responsibilities, not a determination of legal controller
or processor status. Children's data, parental authorization, lawful collection,
provider instructions and any data-processing agreement require **LEGAL REVIEW
REQUIRED** decisions before finalization.

## Acceptable use, content and confidentiality

The proposed use rules are in [Acceptable Use Policy](ACCEPTABLE_USE_POLICY.md).
School-provided educational records, branding and materials remain school content
for operational purposes; this draft does not transfer their ownership to
Paideia. Final ownership, necessary hosting/processing permissions, platform
intellectual-property licensing and third-party rights require **LEGAL REVIEW
REQUIRED**. Confidentiality scope, permitted disclosures, duration and remedies
also require legal review; the technical controls are not a blanket confidentiality
guarantee.

## Availability, support and third parties

No uptime, recovery-time, recovery-point or response-time guarantee is established.
Confirm support channels, hours, escalation and maintenance communication before
signing. Railway hosts the backend/database deployment; Vercel hosts the frontend;
Paystack handles online payments; Cloudinary is configured for image storage.
Configured email/SMS integrations support notifications. Deployment configuration
and successful production upload testing must be confirmed, not assumed.

The [disaster recovery runbook](DISASTER_RECOVERY.md) documents controlled backup
and restore operations. Railway automatic backup frequency and retention still
need confirmation. Cloud-hosted media needs separate backup arrangements; a
database backup does not establish media recovery. Recovery may lose changes
since the selected backup. Do not treat internal recovery targets as an SLA.

## Suspension, termination and changes

Owner suspension preserves school history while blocking normal tenant access.
Payment settlement does not automatically reactivate a suspended school.
Suspension is not permanent data deletion. Contractual suspension grounds,
notice, remediation and reactivation arrangements are **BUSINESS / LEGAL DECISION
REQUIRED**, including how nonpayment is handled; no automatic deletion or
cancellation fee is promised.

Termination notice, remaining balances, refunds, permitted export scope and timing,
transition assistance and eventual deletion require approval under the
[retention/deletion framework](DATA_RETENTION_AND_DELETION_DRAFT.md).
No instant erasure or complete school export facility is promised. Changes to
plans, service or terms require agreed communication and acceptance procedures;
no unilateral variation right is established here.

## Clauses reserved for professional review

**LEGAL REVIEW REQUIRED:** legal identities/authority, governing law, jurisdiction,
children's data, data protection roles, liability/limitations, indemnities,
warranties, confidentiality, intellectual property, disputes, statutory rights,
termination consequences and execution formalities. See the
[Legal Review Checklist](LEGAL_REVIEW_CHECKLIST.md). Signature blocks and binding
acceptance mechanisms must be finalized only after that review.
