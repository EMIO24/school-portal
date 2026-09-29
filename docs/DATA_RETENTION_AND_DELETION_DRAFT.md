# Data Retention and Deletion — draft framework

**LEGAL REVIEW REQUIRED.** No retention period or automatic deletion rule is set.
For every category below: **RETENTION PERIOD — LEGAL/BUSINESS REVIEW REQUIRED**.
Use with the [technical privacy inventory](PRIVACY_AND_DATA_PROTECTION.md) and
[recovery runbook](DISASTER_RECOVERY.md).

| Category | Operational reason | Existing technical behavior | Deletion/anonymization considerations |
| --- | --- | --- | --- |
| Active student records | Enrollment and educational operations | Profiles, linked accounts and academic records persist; email is optional in the approved login change. | Check linked attendance, results, parents and payments; do not cascade-delete as a shortcut. |
| Former student records | Educational history and school administration | Status changes do not establish erasure. | School authority, historic documents and access/export needs need review. |
| Parent accounts | Authorized child access and payment relationships | Explicit parent links and authentication records exist. | Remove/review access separately from historical payment/account records. |
| Staff accounts | Teaching assignments and school administration | Accounts, profiles and assignments persist; access controls can restrict use. | Preserve authorship/history where appropriate; approve account deactivation versus erasure. |
| Optional demographics | School-selected administrative purposes | Existing values persist; restricted access, optional collection. | Minimize collection and decide correction/deletion needs without expanding exposure. |
| Suspended school records | History, operational review and possible restoration of service | Suspension restricts normal tenant access without deleting history. | Termination, export and eventual disposal need a controlled decision. |
| Rejected registrations | Onboarding review and administration | Rejected school registration records remain. | Decide permitted review/history needs and linked administrator treatment. |
| Demo requests | Responding to school enquiries | Submitted contacts/messages persist in DemoRequest. | Decide follow-up closure and secure disposal. |
| PaymentOrder | Verification and reconciliation | Order status, amount, references and relationships persist. | Disputes, accounting needs and linked records require review. |
| FeePayment | School fee accounting and receipts | Payments link to student profiles and schedules. | Preserve receipt integrity; do not erase through unrelated account deletion. |
| Subscription records | School entitlement and purchase history | Plan/end-date state and subscription orders persist. | Address balances, disputes and school closure. |
| Audit/security logs | Diagnostics, access security and traceability | Platform audit records and provider/application diagnostics have different storage paths; no universal retention schedule is established. | Review access, minimization, provider retention and any incident preservation. |
| Uploaded images | School branding and assessment content | Storage URLs reference configured media storage; clearing a reference does not prove provider deletion. | Account for copies, caches, shared references and cloud-provider removal. |
| Backups | Controlled recovery | Backup/restore tooling exists; automatic Railway schedule/retention remains unconfirmed; cloud media needs separate handling. | Decide expiry and restricted handling; prevent unintended restoration of approved deletions. |

## Proposed controlled request process — approval required

1. Verify the requester and school authority through an agreed channel; collect
   only the information needed for the request.
2. Identify relevant records, relationships, exports, provider copies and backups.
3. Obtain business/legal review of retention obligations, any preservation needs
   and whether correction, deactivation, anonymization or deletion is appropriate.
4. Approve a scoped execution plan with access checks, recovery considerations and
   a reviewer before any destructive action.
5. Record the authorized outcome without placing full personal records in logs;
   communicate the outcome using the approved channel and procedure.

This is a proposed governance process, not a deployed deletion service or a
response-time guarantee. Define responsibilities, verification, export scope,
backup handling and any legally required rights before operational adoption.
There are no new deletion jobs. No production data is deleted by this phase.
