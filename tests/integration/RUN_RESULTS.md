# Browser integration run results

Preparation evidence: `.testing/readiness.json`.
Browser execution: **not started**.

Record browser/version, viewport, date, tester and commit before execution. Replace Pending with Pass, Fail or Blocked; include evidence for each result.

| Case | Status | Actual result / redacted evidence / issue |
|---|---|---|
| AUTH-01 | Pending | |
| CSV-01 | Pending | |
| ATT-01 | Pending | |
| ATT-02 | Pending | |
| GRADE-01 | Pending | |
| RESULT-01 | Pending | |
| RESULT-02 | Pending | |
| FEE-01 | Pending | |
| PARENT-01 | Pending | |
| ACCESS-01 | Pending | |
| ACCESS-02 | Pending | |
| ACCESS-03 | Pending | |
| ROUTE-01 | Pending | |
| ERROR-01 | Pending | |
| UI-01 | Pending | |

## Student and document workflow checks

These browser checks remain pending; automated checks do not replace browser testing.

| Case | Action | Expected result | Status |
|---|---|---|---|
| STUDENT-LIST | Open Students; search/filter, paginate and open a profile | Matching students appear; links open the correct profile | Pending |
| CARD-PDF | Generate 12 scratch cards and open the download | Two-page PDF contains 12 serial/PIN cards | Pending |
| CARD-UNUSED | Download Unused Serials PDF for the batch | PDF lists unused serials; no PINs are presented as recoverable | Pending |
| DOCX-IMPORT | Upload fixtures/questions-template.docx in Add Question, review and Save all questions | Two questions preview and save under the selected subject/class | Pending |
| DOCX-EDIT | Upload questions-40.docx, edit a filled question, then Save all 40 questions | Forty separate records are created, including the edit | Pending |
| DOCX-ERROR | Upload a non-DOCX file or document missing an Answer line | Clear error and no questions imported | Pending |

## Automated verification notes

- Browser route audit: 41 authenticated routes at 360 px and 768 px (82 combinations) loaded at their expected URLs with no page-level horizontal overflow or uncaught JavaScript errors.
- Regression coverage includes DOCX parsing and importing 40 distinct question records, editable Word forms, exam rule create/reopen/edit, notification capture, missing-recipient validation and duplicate refresh-token prevention.
- Browser workflow rows above remain for the tester to record actual acceptance results. Local notification capture does not certify SMS/email provider delivery.

### Final verification

- 74 focused frontend tests passed across authentication, student/document workflows and page inventory. The inventory suite passed on rerun after an initial cold-start timeout.
- 13 focused backend tests passed for exam rules, notification capture, DOCX import and scratch-card PDFs.
- Browser checks at 360, 768 and 1280 px confirmed the exam rule form and 40 populated Word question forms without page overflow or uncaught errors.
- A browser-generated debtors download was verified as application/pdf with a valid PDF header.
- Public login/result pages passed checks at 360 and 768 px.
- Live readiness passed: frontend HTML, backend health, all 10 test logins and authenticated profiles.

## Platform management verification

- 7 platform backend tests and 5 CBT/admin regression tests passed (12 total).
- 4 platform frontend tests and 9 authentication regression tests passed (13 total).
- Browser submitted a new school registration, approved it through the owner dashboard, and verified the new school administrator can log in after approval.
- Signup, owner dashboard, school details and create-school pages passed checks at 360, 768 and 1280 px. All 13 captured browser states had no page overflow or uncaught JavaScript exceptions.
- Mobile dashboard and detail screenshots were visually reviewed.
- Frontend development compilation succeeded. Migration drift and whitespace checks passed.
- All 10 original integration accounts still passed login/profile readiness checks.
- Local demo school credentials: `.testing/platform-demo.json`. Owner credentials: `.testing/platform-owner.json`.
- These browser checks used the existing active `qa-school` tenant context. Independent platform routing remains unapplied pending explicit approval; see [routing proposal](PLATFORM_ROUTING_REVIEW.md).

## Platform security and recovery completion

- Routing exemption explicitly approved by the user and applied only to `/api/platform/`.
- 25 backend tests passed across accounts, tenants/MFA/recovery and CBT admin regressions.
- 17 frontend tests passed across platform forms, MFA/recovery screens and authentication state.
- Browser authenticator enrollment and recovery-code login passed using a separate test account. The main owner remains unenrolled so the user can register their own authenticator.
- Owner dashboard and platform staff/activity pages worked with a nonexistent school selected at 360, 768 and 1280 px (six states), without page overflow or uncaught exceptions.
- Native SQLite snapshot/restore drill restored 3 schools, 17 accounts and 74 migration records into `.restores/platform-security.sqlite3`; the live database was preserved.
- Original integration readiness passed: frontend, backend, all 10 school logins and authenticated profiles.
- PostgreSQL backup/restore CI coverage is added but has not run in this session. Docker and PostgreSQL client tools were unavailable locally.
- Production MFA-key configuration, scheduled off-host backups and cloud-upload backups remain deployment setup tasks described in `RECOVERY_GUIDE.md`. Subscription payments/reminders/grace periods remain deferred; plans and renewals stay manual.

## Authenticator setup retry fix

- Pending enrollment now preserves its encrypted authenticator secret across password sign-in retries. A new challenge still invalidates the previous challenge.
- Verification accepts grouped ASCII six-digit codes and rejects non-ASCII digits without a server error.
- Nine backend MFA/security tests passed. The incomplete local owner setup lock was cleared once, with an audit entry; verification remains required and the secret was preserved.


## Paystack integration - 15 September 2026

- Durable fee/subscription orders, authenticated verification, signed webhooks, tenant/student access checks and duplicate-credit prevention implemented.
- School fees require a verified, mode-specific school subaccount; platform subscription payments do not use that subaccount.
- Editable launch prices: Basic NGN 75,000 and Premium NGN 150,000 per 3 calendar months. See SUBSCRIPTION_PRICING.md for assumptions and unimplemented usage billing.
- Backend: 39 fees/tenants/accounts tests passed, including 17 payment regressions.
- Frontend: 12 payment/platform/MFA tests passed across 3 suites.
- Migrations: no model drift; fees 0002 and 0003 applied to the integration database.
- Browser: owner payments and school subscription pages passed at 360px and 1280px with no horizontal overflow or uncaught runtime exceptions. Local evidence: `.testing/payments-ui-results.json` and `.testing/mobile/payments-*.png`.
- Backend restarted with payment routes. Paystack key not provided; real provider checkout, settlement and public webhook delivery remain to be tested using PAYSTACK_GUIDE.md. No live payment performed.

- Production frontend build: compiled successfully after removing a stale generated ESLint cache; no bulk-import source change was necessary.


## Feature plans and school designs - 15 September 2026

- Owner design studio: `/superadmin/appearance`. Five assignable layouts: Scholar, Campus, Studio, Executive and Heritage. Includes colour controls, typography, logo URL, motto, preview and manual plan activation.
- Setup/Basic/Premium features enforced by backend middleware and frontend route/menu guards. Billing verification and historical fee receipts retain normal authorized access. Renewal dates remain manually managed.
- Backend: 54 tenants/fees/accounts/CBT workflow tests passed, including 10 plan/branding tests. No migration drift.
- Browser: 18 layout/editor/menu/feature-lock states passed at 390px and 1440px; two additional sign-in preview states passed. No horizontal overflow or uncaught runtime errors. Cross-school preview preserved the owner session.
- Visual review corrected welcome-banner text contrast. School theme cache is now scoped to the selected school.
- Final production frontend build compiled successfully.
- Local evidence: `.testing/designs-ui-results.json`, `.testing/preview-ui-results.json`, `.testing/mobile/design-*.png` and `.testing/mobile/school-signin-preview-*.png`.
- Local QA schools have Premium for integration testing; other schools retain their assigned plans. No card charged.

- Final combined frontend regression run: 60 tests passed across 11 suites. Live readiness passed: frontend, backend, 10 logins and 10 authenticated profiles.


## User guides and mobile usability fixes - 15 September 2026

- Complete guide for platform owners, school administrators, staff/teachers, parents and students, plus getting-started and troubleshooting sections. Read it at `/help` before sign-in, `/user-guide` for school users, or `/superadmin/guide` for platform owners.
- Role-specific and complete PDF downloads are available in the portal. Standalone artifact: `docs/school-portal-user-guide.pdf` (8 pages; PDF header/trailer checked). Markdown: `docs/USER_GUIDE.md`.
- All five layouts now use a compact phone/tablet header and fixed slide-out menu through 1024px. The menu supports Escape, focus containment, backdrop dismissal and restores page scrolling when closed.
- Improved mobile text sizes, input sizing, single-column cards on narrow phones, form layout, table/timetable scroll containment and non-overlapping design save controls.
- Baseline measurement found desktop navigation still active at 768px for all five layouts. Final checks verified a mobile drawer there.
- 50 browser checks passed across five designs at 320px, 390px and 768px: student forms, menus, timetables, guides and the design editor. One additional public-help check passed without a valid school selected. No page-wide horizontal overflow or uncaught runtime errors in these checks.
- 38 frontend regression tests passed across guide, design, login, route and theme suites. Live readiness passed frontend/backend health, 10 logins and 10 authenticated profiles.
- Browser evidence: `.testing/mobile-usability-results.json`, `.testing/mobile-before.json`, and `.testing/mobile/mobile-*.png`.

## Guide download location
- PDF guide downloads are available only on /superadmin/guide. School user guides and /help remain available for reading.
- 13 guide tests passed; download controls require both the superadmin route option and the superadmin role.
