# Managing schools as the platform owner

## Open the platform

- Owner login: http://127.0.0.1:3001/platform/login
- Owner dashboard: http://127.0.0.1:3001/superadmin/dashboard
- School registration: http://127.0.0.1:3001/register-school
- Local owner credentials are in `.testing/platform-owner.json`. They belong only to the isolated integration database. Keep this file out of Git.
- To create your own owner interactively in this sandbox: `python backend/manage.py createsuperuser --settings=config.settings.integration`.

The owner account has no school and uses the `superadmin` role. Ordinary school-admin accounts cannot manage other schools.

## Create and manage schools

1. Sign in as the platform owner and choose **Create school**.
2. Enter the school details, a unique lowercase school identifier, and its first administrator's details and temporary password.
3. Save. The school is approved and active. Share the administrator credentials securely; the administrator must change the temporary password on first login.
4. Use **Manage [school name]** to change contact details, plan, renewal date and owner notes, or to add/disable administrators. The last active administrator cannot be disabled.
5. Share the **School login link**. It selects the school for that browser tab. Changing schools through a login link signs out the previous session.

## Review registrations

1. A school submits the public registration form with its administrator's chosen password.
2. It appears under the **pending** status filter. Its accounts cannot access the school portal yet.
3. Review the details, then **Approve school** or **Reject school**.
4. After approval, the administrator can sign in with their chosen password. Contact the applicant separately: approval does not send an email automatically.
5. **Suspend school** blocks school portal access, including existing authenticated sessions. Records are retained. **Activate school** restores access for an approved school.

## Subscription and usage

Free, basic and premium plans and renewal dates are administrative records. This implementation does not charge cards, apply plan feature limits or suspend schools automatically when a date expires. Use owner notes to record manual payment/renewal arrangements and suspend access explicitly when appropriate.

The dashboard displays account counts, including student, teacher and administrator accounts. These are not attendance, payment, storage or active-user analytics. Recent activity records owner changes and registration submissions; passwords are never included.

## Platform access and two-factor authentication

The routing change is approved and applied. Owner login, school registration and platform management work even when the selected school does not exist or is suspended. School-specific APIs still require an active school and matching account membership.

1. Open http://127.0.0.1:3001/platform/login and enter the credentials from `.testing/platform-owner.json`.
2. On first login, add a time-based account in your authenticator app. Scan the QR code or enter the displayed setup key manually.
3. Enter the current six-digit code. Save all eight recovery codes privately before clicking **I saved my codes - continue**.
4. Future sign-ins require your password plus an authenticator code or one unused recovery code. Codes cannot be reused. Five incorrect codes lock verification for 15 minutes; a login challenge expires after five minutes.
5. The older Django admin login also requires an authenticator or recovery code. Existing owner sessions issued before this change are rejected.

Your main owner account is deliberately not enrolled by the automated tests: you must enrol your own phone. Browser verification uses a separate test account. No email/SMS delivery is involved in MFA.

## Platform staff and detailed activity

Open **Platform staff and activity** in the navigation menu.

- **Read only:** can view school information, but cannot approve, suspend, change subscriptions, add administrators or manage platform accounts.
- **Owner:** can manage schools and platform accounts. Grant this only to trusted colleagues who need those powers.
- Each account has its own email, temporary password and authenticator. New accounts must change their temporary password. New platform accounts do not receive Django admin access.
- You cannot disable your own account. Disabling or re-enabling another account revokes its old sessions.
- Activity records include the actor, timestamp, target, source IP, school changes with before/after values, staff access changes, MFA attempts and successful platform logins. Passwords, authenticator secrets and recovery codes are excluded. Legacy Django admin changes remain in Django's own admin log.

## Backups and recovery

See [the backup and recovery guide](RECOVERY_GUIDE.md). Local restoration has been tested into a separate SQLite database; PostgreSQL restoration is included in CI but could not be executed locally because Docker/PostgreSQL tools were unavailable.

## Acceptance checklist

- [ ] Sign in as the owner; confirm the existing schools and account counts appear.
- [ ] Create a school and its administrator; sign in using the school login link and change the temporary password.
- [ ] Submit another school through public registration; confirm sign-in is denied before approval.
- [ ] Approve the registration; confirm its administrator can sign in.
- [ ] Change a plan and renewal date; refresh and confirm they persist.
- [ ] Add a second administrator; disable the first and confirm the last-active-admin guard.
- [ ] Suspend a test school and confirm its accounts lose access; reactivate it.
- [ ] Sign in as a school admin; confirm owner pages and management APIs are inaccessible.
- [ ] Review signup and management on a mobile screen.
- [ ] Repeat owner login and school signup without an active school selected.
- [ ] Enrol your authenticator and save the recovery codes.
- [ ] Create a read-only platform account; confirm it cannot change school data.
- [ ] Review activity records after changing a subscription.
- [ ] Follow the recovery guide to restore a backup into a new destination.
