# Commercial Launch Checklist

Phase 7 prepares drafts only. These are release prerequisites, not instructions
to execute a production deployment now. Record owner, evidence and approval for
each item. An unchecked item is not represented as completed.

## Operational prerequisites

- [ ] Cloudinary Railway environment variables configured through secure settings.
- [ ] School logo upload tested against production storage.
- [ ] CBT image upload tested against production storage.
- [ ] Migration `accounts.0005_optional_student_email` reviewed and applied during
  controlled deployment; it has not been applied as part of Phase 7. Resolve NULL
  student emails safely before considering a rollback to the old required field.
- [ ] Student-name login production smoke test, including duplicate names,
  school boundaries, admission numbers and existing email logins.
- [ ] Railway automated backup frequency/retention confirmed and recorded.
- [ ] Cloud-hosted media backup/recovery responsibility confirmed separately.
- [ ] Vercel frontend deployment verified with root `frontend`, development build
  dependencies installed, `npm run build` and output `build`; verify preview first.
- [ ] Paystack LIVE readiness completed before real-money launch.
- [ ] Controlled real-money transaction performed only when explicitly approved.
- [ ] Agreed school support and incident-reporting channels confirmed.

## Commercial/legal prerequisites

- [ ] Final legal review completed using [Legal Review Checklist](LEGAL_REVIEW_CHECKLIST.md).
- [ ] Legal entity, contracting authority and official contact information verified.
- [ ] School service schedule agreed: plan, active-student count, billing term and
  the configured subscription duration; maintain Basic ₦800 / Premium ₦1,500 per
  active student per term and the automatic 10% discount at 100+ active students.
- [ ] Retention/deletion policy approved, including backups and uploaded media.
- [ ] Refund policy approved, including school-fee versus subscription responsibility.
- [ ] Data responsibilities, children's data and optional demographics reviewed.
- [ ] Suspension/termination, exports and support arrangements approved.
- [ ] Final public policy versions and acceptance procedures approved and recorded.

Student-login carry-over: `db9a6e1` — implementation/tests passed and commit pushed.
This does not establish that the migration or new login flow is deployed.
No production change, LIVE switch or financial transaction is authorized by a
checkmark template. Do not begin Phase 8 as part of this documentation work.
