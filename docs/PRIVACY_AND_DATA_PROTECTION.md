# Privacy and data protection — Phase 6

This is an operational inventory and description of technical controls, not a
legal certification or final privacy policy.

## Stored data and purpose

| Category | Existing records and use |
| --- | --- |
| Students | Names, email, admission identifiers/dates, date of birth, gender, state of origin, profile image reference, class/status and guardian contacts support enrollment and school administration. |
| Parents | Account/contact details and explicit parent–student links support child access. Login challenges store hashed codes, expiry and attempt state. |
| Staff | Account/contact details, address, demographics, employment, qualifications and teaching assignments support school administration and teaching. |
| Academic | Attendance/status/remarks, scores, result remarks/positions, affective and psychomotor ratings support educational reporting. These ratings are ordinary school report fields; no new sensitive collection is introduced. |
| CBT | Answers, scores, timing, question snapshots, tab-switch counts and session IP addresses support assessment delivery and integrity. |
| School and enquiries | School contacts, branding, registration/approval, subscription configuration, administrative accounts, internal platform notes and demo enquiry contacts/messages support service operations. |
| Payments | Fee schedules/payments, receipts, orders, amounts, payer relationships, provider references and subscription records support billing and reconciliation. Paystack processes online payments. |
| Authentication/security | Password hashes, token/blacklist state, encrypted platform MFA secrets, recovery hashes, challenge state and access flags support authentication. Platform audit events include actor/contact identifiers, IP addresses and action-specific details. |

### Religion: Sensitive optional demographic information

StudentProfile.religion and StaffProfile.religion remain optional, including
registration and onboarding. Paideia does not require them for core portal
functionality. Schools determine whether they have an appropriate administrative
reason to collect them. This document does not establish a legal basis.

Existing school administrator forms, profile details and optional student import
support administrative management. School administrators may access their own
school's values; staff may view their own value through the existing detail API.
Student account profiles do not expose religion. Teachers do not receive student
religion merely because they teach them. Parent responses, ordinary directories,
public responses, login, analytics, dashboards, payments and search results omit it.
Platform viewers do not receive it through staff detail responses. Serialization
without a requesting user also omits it. Existing documents do not include it;
any future export would require a specific need and authorized requesting role.
Values must never be included in application or observability logs.
No fields or stored values were deleted and no migration was required.
Retention/deletion remains a policy/legal decision.

## Implemented technical controls

- Tenant querysets and role permissions scope school records. Student class and
  staff assignment relations are validated against the requesting school, using
  the existing relation validator. School selection alone does not grant access.
- School administrators manage school records. Existing teacher directory access
  remains available; student religion and other staff members' private contact/
  demographic fields are excluded. Staff detail reveals those private fields only
  to the same-school administrator or the staff member.
- Parent access requires an explicit school-scoped ParentStudentLink. Student
  result, attendance, fee and analytical access uses the student's own identity.
  Parent dashboard score summaries now include published scores only.
- Score mutations require existing subject/class/term assignments for teachers.
  Existing school administrators retain their administrative permissions.
- Platform administration is separate from school APIs. Platform viewers remain
  read-only; owner audit/account operations retain their owner permissions.
  Public school responses do not include platform notes or security state.
- Public school lookup returns a minimal match/slug response. Public branding
  includes presentation fields and the existing plan feature catalog used by the
  portal, not user lists, billing records or administrator contact information.
  Result checking requires the existing scratch-card credentials and admission
  identifier; it is not an unrestricted student lookup. Health remains minimal.
- Protected result slips, transcripts and receipts authorize the requester and
  tenant before rendering. Exported copies must be handled as private records.
- School-facing payment responses use limited fields and existing ownership
  checks; provider credentials and raw verification payloads are not returned.
  Settlement, reconciliation and subscription extension were not changed.
- Request correlation and payment diagnostics use IDs/statuses rather than full
  request bodies. Existing regression tests cover exception-message redaction,
  payment customer-data exclusion and webhook signature/body exclusion. Do not
  add religion, credentials, tokens, sensitive notes or full records to logs.
- Images are stored through the existing configured storage service and referenced
  by URLs. Protected API authorization is not a claim that a copied image URL is
  private. Do not use the existing public media upload facility for confidential
  documents. No storage architecture was changed.
- School suspension and supported administrator/account deactivation preserve
  records while restricting access. Existing model deletion can cascade into
  educational records; deactivation must not be confused with erasure. This phase
  adds no account deletion interface or deletion automation.

## Regression evidence

`accounts.test_privacy` covers optional demographics, retained values, role-based
responses, foreign-school enrollment relations, parent/student results, document
authorization before rendering, published dashboard summaries and assigned teacher
mutations. Existing attendance, fees, readiness, platform security, public lookup
and observability suites cover the equivalent boundaries without duplicate tests.

## Policy/legal decisions still required

Retention periods must be finalized before commercial launch based on operational,
contractual and applicable legal requirements. Categories include former students,
staff/parent accounts, optional demographics, suspended schools, rejected
registrations, demo requests, academic/assessment records, payments, audit/security
logs, uploaded media, backups and deleted accounts. No period is specified here.

Controlled deletion/anonymization must account for linked results, attendance,
payments, audit history, exports and backups. Collection grounds, privacy request
procedures, support contacts and the public privacy draft require business/legal
review. No legal compliance, certification or response-time guarantee is claimed.
