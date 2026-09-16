# School portal production readiness audit

Date: 2026-09-15
Decision: **STAGING/DEPLOYMENT CANDIDATE after remediation. Do not accept real school records or live payments until production secrets, Paystack/Termii/Brevo accounts, backups and restore drills are verified in the target hosting environment.**

This audit covers the current working tree, including uncommitted changes. It combines source review with disposable database reproductions, application tests, migration checks and a frontend production build. Findings below distinguish reproduced defects from source-inspected risks and operational work still requiring staging evidence. No production records were modified and no real SMS, email or payment was sent. This is not a certification or a complete penetration test.

## Remediation status - 2026-09-15

The critical defects reproduced in this audit have been remediated in the current working tree and are now covered by automated checks. The historical findings below are retained so reviewers can see what was fixed and why the acceptance tests exist.

| Check | Current result |
| --- | --- |
| Backend suite | 86 tests passed |
| Production-readiness probes | 16 checks passed |
| Frontend suite | 26 suites passed, 239 tests passed with CRA/Jest `--forceExit` because the legacy test runner keeps an open handle after completion |
| Frontend production build | Passed; `BulkImport.jsx` `filename` error cleared after fixing source and clearing stale cache |
| Django system check | Passed: no issues |
| Migration consistency | Passed: no changes detected |
| Python dependency audit | Passed: no known vulnerabilities |
| Frontend runtime dependency audit | Passed: 0 vulnerabilities with `--omit=dev` |

Verified commands from the repository root:

```powershell
.venv-release\Scripts\python backend\manage.py test accounts academics enrollment tenants fees cbt gradebook results attendance timetable analytics promotion notifications --settings=config.settings.test --noinput
.venv-release\Scripts\python backend\manage.py makemigrations --check --dry-run --settings=config.settings.test
.venv-release\Scripts\python backend\manage.py check --settings=config.settings.test
.venv-release\Scripts\python scripts\audit_readiness.py
.venv-release\Scripts\pip-audit -r backend\requirements.txt
npm --prefix frontend test -- --watchAll=false --runInBand --silent --forceExit
npm --prefix frontend run build
npm --prefix frontend audit --omit=dev
```

Deployment preparation completed in this remediation pass includes stronger tenant/role enforcement, OTP redaction and challenge handling, exam timing/snapshot protection, grade validation, protected fee receipts, notification outbox idempotency/recovery, production preflight checks, Docker/CI dependency hardening, and a patched React Router runtime. The app is ready for a staging deployment rehearsal; use [STAGING_DEPLOYMENT_CHECKLIST.md](STAGING_DEPLOYMENT_CHECKLIST.md) and [RAILWAY_VERCEL_DEPLOYMENT_GUIDE.md](RAILWAY_VERCEL_DEPLOYMENT_GUIDE.md). The final live-production gate is operational: configure real secrets outside the repo, run migrations against the target database, verify Paystack split settlement in test mode, send controlled Termii/Brevo test messages, and complete backup/restore proof on the hosting database.
## Original baseline verification results

| Check | Result |
| --- | --- |
| Backend suite, run from backend | 70 tests: 69 passed, 1 failed |
| Frontend suite | 300 tests: 222 passed, 78 failed; 5 of 26 suites failed |
| Added audit probes | 16 checks: 15 failed security/business expectations, 1 passed |
| Frontend production build | FAILED: undefined `filename` in `frontend/src/components/admin/BulkImport.jsx:101` |
| Model/migration consistency | Passed: no changes detected |
| Backend discovery from repository root | Fails importing root `test_login.py`: database query runs before test database creation |

The original 15 failed audit checks did not mean 15 independent vulnerabilities: several demonstrate different consequences of the same missing authorization boundary. The passing audit check confirms that a rotated refresh token cannot be reused in the tested configuration.

Commands, from the repository root:

```powershell
python scripts/audit_readiness.py
Push-Location backend
python manage.py test --settings=config.settings.test --noinput
python manage.py makemigrations --check --dry-run --settings=config.settings.test
Pop-Location
npm --prefix frontend test -- --watchAll=false --runInBand --silent
npm --prefix frontend run build
```

The audit script deliberately asserts required safe behavior. At the baseline audit it exited nonzero; after remediation it passes and should remain in CI. It uses in-memory SQLite, synthetic schools, real JWT authentication and mocked SMS transport. It does not require the integration server or use its database. Keep these checks and incorporate them into CI as defects are repaired.

Local run evidence: `.testing/audit-reproductions.log`, `audit-backend-apps.log`, `audit-frontend.log`, `audit-build.log`, `audit-migrations.log`, and `audit-backend.log`. These are local evidence files, not a public report containing credentials.

## Findings requiring fixes before launch

### A01 - CRITICAL: school isolation and role authorization are missing in multiple APIs

**Reproduced.** With a valid student JWT from School A and School B selected in `X-School-Slug`, the gradebook endpoint returned HTTP 200. A student in School B could delete a grade through the normal endpoint (HTTP 204). School A's student could retrieve School B's question, including `correct_answer`, and read its notification logs.

Sources: `backend/tenants/middleware.py` resolves the caller-selected school; `backend/tenants/mixins.py` scopes querysets to that school but does not check user membership; `backend/gradebook/views.py:50`, `backend/cbt/views.py:63`, `backend/cbt/views.py:197`, and `backend/notifications/views.py:139` use `IsAuthenticated` without the required tenant/role restrictions.

The same source-level pattern exists in results (`backend/results/views.py:276`, `:356`, `:412`), attendance (`backend/attendance/views.py:77`), timetable (`backend/timetable/views.py:58`), analytics (`backend/analytics/views.py:22`) and promotion (`backend/promotion/views.py:92`). Those additional operations were inspected, not individually exploited in this audit.

**Fix:** enforce school membership centrally for every school API, then enforce roles and object access per operation. Restrict grade/exam administration to authorized staff, students to their own records, and parents to verified linked children. Teachers need subject/class assignment checks. Platform management must retain its separate owner-only permission boundary. A hidden menu or paid-plan check is not authorization.

**Acceptance:** a role-by-endpoint test matrix covers list/detail/create/update/delete/custom actions, foreign school headers and foreign object IDs. Unauthorized attempts return 403/404 without changing data or revealing answer keys.

### A02 - CRITICAL: parent login codes are stored in exposed notification logs

**Reproduced with mocked SMS transport.** Requesting a parent OTP stores the SMS message body in `NotificationLog`; a student from another school can retrieve the log and its login-code text. This combines authentication-secret logging with A01 and creates a parent-account takeover path while a code is valid. No real parent's code was used.

Sources: `backend/accounts/views.py:208`, `backend/notifications/services/termii.py:10`, `backend/notifications/views.py:139`.

Additional source findings: parent OTP request/verify views have no explicit throttles or attempt limit; cache keys contain only the phone, not the school; OTP generation uses `random.choices`; request handling accepts phone numbers without confirming a valid school/eligible parent first. These permit abuse and cross-school challenge collisions. Public scratch-card PIN verification also lacks an explicit throttle.

**Fix:** never persist authentication codes in general-purpose message logs; redact existing retained OTP messages according to a controlled cleanup plan. Add school-scoped challenges, cryptographic generation, short expiry, atomic consumption, retry/send limits and recipient eligibility checks. Return generic responses that do not enumerate parents. Restrict notification logs to authorized school staff.

**Acceptance:** no API/log contains OTP plaintext; codes cannot cross school boundaries, be reused, or survive their retry limit; unauthorized phone requests cannot generate unrestricted SMS costs.

### A03 - HIGH: exams do not enforce eligibility and deadlines on the server

**Reproduced.** An exam scheduled for tomorrow starts now. An unassigned student from another school can start it. An answer submitted an hour after a ten-minute session started is persisted with HTTP 200.

Sources: `backend/cbt/views.py:259` checks publication status but not the timetable or assigned class; `:320` saves answers; `_get_active_session` near `:615` checks completion status without calculating deadline expiry.

Source-inspected related issues: submit always returns a `score` even when `show_score_immediately` is false (`:371`); scoring reads mutable question-bank records (`backend/cbt/services.py`); random selection silently returns fewer questions when a pool is too small (`backend/cbt/models.py`, `resolve_questions`).

**Fix:** enforce student membership/class, opening and closing times, and the individual duration on every exam operation. Finalize expired sessions server-side with locking. Snapshot question text/options/answer keys for each attempt. Honor score/review-release rules in every response. Reject incomplete question pools before publication.

**Acceptance:** early/late/unassigned attempts fail; late autosaves cannot change marks; concurrent submit/save is consistent; editing the question bank cannot change an existing attempt's score.

### A04 - HIGH: bulk grades permit foreign relationships and negative marks

**Reproduced as a legitimate School B administrator.** Bulk update created a School B grade linked to a School A student. Another bulk request saved an exam score of -10 with HTTP 200. These defects remain even after replacing student permissions.

Sources: `backend/gradebook/serializers.py:140` and `:157` accept integer IDs and decimals without tenant relationship checks/minimum bounds; `backend/gradebook/views.py:92` upserts those IDs and checks upper limits only.

**Fix:** validate every student, class, subject, term and session against the tenant and against each other, including class enrollment and teacher assignments. Enforce lower and upper score bounds. Define atomic versus partial-save behavior and surface every rejected row. Lock published results except through an audited correction workflow.

**Acceptance:** foreign/mismatched IDs and negative scores leave no changed rows; valid marks still save; publication and subsequent corrections have clear permissions and history.

### A05 - HIGH: decimal scores can be incorrectly graded as failures

**Reproduced.** Saving 54.50 assigns `F9 / Fail`. Default grade bands end at 54 and restart at 55, leaving decimal gaps; unresolved scores fall back to failure.

Sources: `backend/gradebook/models.py:78` and `:205`.

**Fix:** use continuous boundaries (or an explicitly agreed rounding policy) and migrate existing school grade scales. Recompute affected results with an audit record, not an unannounced historical overwrite.

**Acceptance:** boundary tests include 39.99, 40, 44.50, 54.50, 74.99, 75 and 100, as well as each school's configured grading scheme.

### A06 - HIGH: deleting a fee category erases payment receipts

**Reproduced.** A school administrator deleted a paid fee category (HTTP 204); its payment record was removed.

Sources: `backend/fees/views.py`, `FeeCategoryDetailView.delete`; `backend/fees/models.py:23` and `:42` use cascading category -> schedule -> payment relationships.

**Fix:** archive used categories/schedules, protect ledger records from cascading deletion, and use explicit credit/refund/reversal records. Review student/class/session deletion for similar historical-data loss. Paystack order retention alone does not preserve the complete school receipt ledger.

**Acceptance:** deleting or archiving referenced setup data never removes a receipt or changes previously issued balances; corrections remain attributable and auditable.

### A07 - HIGH: changing a school user's password does not revoke old refresh tokens

**Reproduced.** A refresh token issued before a school student's password was changed still obtained a new access token (HTTP 200). Refresh rotation itself passed the separate replay test.

Sources: `backend/accounts/serializers.py`, `ChangePasswordSerializer.save`; `backend/accounts/authentication.py`; `backend/tenants/security.py:44` applies session-version checks only to superadmins. Base settings give refresh tokens a seven-day lifetime.

**Fix:** add account-wide session/password revocation for school users and a logout-all-sessions mechanism. Enforce mandatory password change at the API boundary with narrowly scoped exceptions for changing it.

**Acceptance:** old access/refresh sessions lose access after the agreed revocation events; the legitimate password-change flow remains usable.

### A08 - HIGH: public scratch-card checking is blocked by plan middleware

**Reproduced.** An empty request with a valid school header to `/api/results/check/` returns 404 from middleware instead of reaching the view's 400 input validation.

Sources: `backend/tenants/middleware.py` exempts the public checker and sets tenant to None; `backend/tenants/plans.py:25` classifies `/api/results/` as a tenant-required results feature. Therefore the request is rejected before the checker resolves the card's school.

**Fix:** handle the public checker deliberately in both middleware layers. Resolve the school from the card and enforce approval/suspension/public-result policy in the view. Add valid-card, invalid-card, suspended-school and replay tests.

### A09 - HIGH: the current tree cannot produce a frontend release build

**Build reproduced.** ESLint fails at `frontend/src/components/admin/BulkImport.jsx:101`: `filename` is not defined.

The full frontend suite also fails 78 checks. Inspected examples include missing ThemeProvider setup for AdminDashboard tests, old dashboard heading expectations and an outdated notification summary expectation. These are not proof that 78 separate screens are broken. They are proof the regression gate is currently unreliable.

The backend failure expects CSV attendance output although the product now returns PDF (`backend/enrollment/test_import_contracts.py:68`). Root `test_login.py` queries the database at import time and breaks repository-root test discovery.

**Fix:** repair the undefined variable; update stale tests to verify the intended PDF/design contracts; add required test providers; move diagnostic script execution behind a main guard. Do not disable ESLint, remove assertions or exclude failing suites to obtain a green release.

**Acceptance:** production build, complete backend/frontend suites, API contract audit and the new security probes all pass in CI on the same locked dependency set.

### A10 - HIGH: production dependency and transport hardening is incomplete

**Environment/source inspected.** This workstation runs Django 4.2.16, DRF 3.15.2 and SimpleJWT 5.3.1. Most entries in `backend/requirements.txt` are unpinned, so a fresh build may install a different framework from the one tested locally. The installed Django 4.2 line is no longer supported as of this audit date; see [Django's support table](https://www.djangoproject.com/download/) and [4.2 documentation warning](https://docs.djangoproject.com/en/4.2/releases/). No specific exploitability claim is made for every dependency.

`backend/config/settings/production.py:51` explicitly passes `ssl_cert_reqs=None` to Redis, disabling certificate verification for that connection. Celery SSL settings at lines 60-61 also need validation against the effective namespaced Celery configuration. See [Celery SSL configuration](https://docs.celeryq.dev/en/main/userguide/configuration.html).

CORS regexes at line 77 trust unrelated sites across entire hosting-provider domains. This alone does not give an attacker a bearer token, but it broadens the browser trust boundary unnecessarily. Django-side HTTPS redirect is not configured here; actual edge HTTPS enforcement was not verified.

**Fix:** lock compatible supported versions, run vulnerability checks, verify TLS certificates, restrict production origins/hosts, and run deployment checks against actual staging settings and proxy headers. Verify the deployed image's versions rather than assuming the workstation matches production.

## Operational and school-workflow gaps

These items require implementation or explicit operating procedures before a pilot; source-only findings are identified accordingly.

| Area | Finding and required behavior |
| --- | --- |
| OTP delivery | Reproduced: mocked provider failure still returns `OTP sent.` from `accounts/views.py:240`. Check delivery results and distinguish accepted, failed and delivered without enumerating accounts. |
| Bulk notifications | Source: `notifications/views.py` sends per recipient synchronously; provider calls can take 15 seconds each. Use durable queued jobs, idempotent recipient handling, progress and retries so browser timeouts do not cause repeated sends or charges. Provider HTTP acceptance is not proof of handset/inbox delivery. |
| Payment recovery | Source: `fees/payments.py:34` preserves an initializing order on initialization failure; pending/initializing/review orders block subsequent checkout at lines 137 and 203. Verification helps valid references, but a reference never created at Paystack lacks a clear safe terminal resolution. Provide audited reconciliation/cancellation after provider checks, review-case ownership, and refund handling. Never release a pending order merely because the browser timed out. |
| Renewals and suspension | Source: `tenants/plans.py` checks plan name, not subscription end date. This matches the current manual-renewal approach but needs an owner renewal queue and documented expiry/grace policy. Decide access to records/receipts during suspension and expiry; do not introduce automatic payment-based reactivation. |
| Analytics correctness | Source: `analytics/tasks.py:58` uses different grade cutoffs from GradeScale; line 84 sums fee schedules once rather than per liable student, so collection percentage can exceed 100% with multiple students. Line 49 groups historical scores by current class, so promotion changes historical grouping. Use one grading policy, real assessed liabilities and historical enrollment. |
| Promotion and year rollover | Source: `promotion/views.py:110` chooses the newest other session, which may be an older session; execution creates records without a batch transaction or idempotency constraint. Require explicit destination session, validated decisions, preview/approval, replay protection and preserved historical enrollment. |
| Results approval | Define teacher entry -> review -> publication -> audited correction. Current publication is a bulk flag operation and broad access is covered by A01. Test missing marks, absent/exempt students, ties, optional subjects and school-specific grading. |
| Roles in a real school | Current role set needs either clear operating limits or scoped permissions for bursars, registrars, heads of department and examination officers. Avoid giving every staff member broad school-admin rights to perform one job. |
| Parent onboarding | Demonstrate verified guardian-to-child linking, multiple children, guardians shared between schools, changed phone numbers and disabled accounts. A successful OTP must not imply access to all children. |
| Historical fees | Prove that promotion, transfers, fee changes and withdrawal preserve prior invoices, arrears and receipts. Define discounts/scholarships, installments, overpayments, credits/refunds and reconciliation responsibilities. |
| Recovery | `tenants/recovery.py:41` backs up the database and local media only; line 77 explicitly excludes cloud assets. A production PostgreSQL + Cloudinary + MFA-key restore, encrypted off-site retention, monitored schedules and recovery time/data-loss targets still need evidence. Existing local recovery tests are useful but insufficient for a production recovery claim. |
| Release operations | The workflow has backend/frontend gates and a PostgreSQL restore drill, but those gates are not currently green. Require successful deployed health checks, migration rollback/forward procedures, error monitoring and operator alerts. |

## Controls observed that should be retained

- Platform routes have separate owner/member permissions and MFA/session-version checks; manual registration approval and suspension handling have dedicated tests in the backend suite.
- Payment settlement uses server-side verification and idempotent success handling; webhook signatures are checked. Keep these controls while addressing operational reconciliation.
- Refresh rotation replay protection passed the audit probe.
- Model/migration consistency passed. Backup helpers verify checksums and avoid overwriting configured databases.
- The tracked-path check returned no `.testing`, `.env`, PEM/key or SQLite files. This was a narrow filename check, not a full secret scan of content, Git history, built bundles or deployed assets.

## Release acceptance checklist

1. Fix A01/A02 first. Run the full role/tenant/object authorization matrix and confirm no authentication secrets reach logs or APIs.
2. Fix exam timing, grading and ledger preservation. Pass the audit probes and review whether any real historical data needs correction.
3. Repair the build and test contracts; use the same supported, locked dependencies in local testing and CI.
4. Run staging with two schools and separate owner/admin/teacher/parent/student accounts. Complete admission, class placement, attendance, marks approval, results/PDFs, fees/receipts, promotion and withdrawal. Verify both successful and interrupted workflows.
5. Use Paystack test mode to verify separate-school settlement routing, duplicate webhooks, timeouts, abandoned checkout, balance changes and refund/reconciliation handling. Verify email/SMS failure and retry handling without contacting real families.
6. Restore a production-like PostgreSQL backup and cloud assets into a separate environment; verify school separation and owner MFA access after recovery.
7. Repeat browser checks across all five layouts on actual mobile browsers, including long names/tables, keyboards, offline/slow requests and interrupted exam saves. Earlier responsive work is not a substitute for this release's end-to-end checks.
8. Start a controlled pilot only after the critical/high findings are closed and the remaining workflow limitations have a named operator and an agreed procedure.

## Limits of this audit

No live infrastructure penetration testing, real Paystack settlement, provider delivery, complete dependency vulnerability scan, full historical secret scan, load testing, PostgreSQL concurrency reproduction, or fresh all-device browser matrix was performed. These remain required staging/operational evidence, not assumed passes. Findings describe the reviewed working tree and must be rechecked after fixes.

Only the audit report and disposable regression script were added by this audit. Application vulnerabilities remain open; no production-readiness claim is made.




