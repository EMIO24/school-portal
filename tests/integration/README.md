# Test the portal with sample data

This guide lets you sign in as an administrator, teacher, student or parent and try the portal with sample school data. "Integration testing" here means checking that actions in the browser save correctly and appear for the right users.

## Start here

**Docker can stay open.** This test setup uses its own database and runs separately from Docker. Open **http://127.0.0.1:3001** for these sample accounts. The normal Docker app at port 3000 does not use this sample database.

1. In VS Code, select **Terminal > New Terminal**. Use PowerShell.
2. Run the following commands to create the sample data and start the test backend:

   ```powershell
   cd C:\Users\user\school-portal
   python scripts/integration.py prepare
   python scripts/integration.py serve
   ```

   Wait for `Readiness passed` after preparation. The second command keeps running; leave this terminal open.

3. Select **Terminal > New Terminal** again. Start the test website:

   ```powershell
   cd C:\Users\user\school-portal
   npm --prefix frontend run start:integration
   ```

   Leave this terminal open too. Wait until the frontend finishes compiling.

4. Open a private/incognito browser window at **http://127.0.0.1:3001**. Sign in with:

   - **Email:** `school_admin@qa-school.test`
   - **Password:** `PortalTest!2026`

You do not need to import a file to get started. Preparation already creates two students, a teacher, a parent linked to one student, class **JSS1 A**, **Mathematics**, session **2026/2027**, **First Term**, a Monday timetable lesson and a **15,000 tuition fee schedule** in QA School. It also creates a second school for checking school isolation.

Attendance, grades and payments are records you create while testing; preparation does not prefill completed workflows. A fee schedule is the configured charge, not a recorded payment. The timetable sample is on Monday, so other days may be empty.

## Your first test session

All accounts below use **`PortalTest!2026`**. Log out before switching accounts.

| Step | Sign in as | What to try |
|---|---|---|
| 1 | `school_admin@qa-school.test` | Open students, staff and school setup. Find the sample students, teacher, JSS1 A and Mathematics. |
| 2 | `teacher@qa-school.test` | Open attendance, choose JSS1 A and a date, mark a student absent, add a remark and save. Reload to check it stayed saved. |
| 3 | `teacher@qa-school.test` | Open score entry. Choose 2026/2027, First Term, JSS1 A and Mathematics. Enter scores within the limits shown, save a draft, then publish when ready. |
| 4 | `student@qa-school.test` | Open attendance and results. Check the saved attendance and published marks for that student and term. |
| 5 | `school_admin@qa-school.test` | Open fee collection. Select the sample student and term, record a manual tuition payment, then check the balance and receipt. |
| 6 | `parent@qa-school.test` | Use Email on Parent Login. Open the linked child's results and fees and compare them with the records you just created. |

To try CSV imports as the administrator, upload `tests/integration/fixtures/staff-valid.csv` for staff and `tests/integration/fixtures/students-valid.csv` for students. Each adds one person. The other CSVs intentionally contain errors; see the table below.

To stop testing, press **Ctrl+C** in each server terminal. Your sample data stays saved. Next time, run the backend and frontend commands again; you only need `prepare` to create or repair the starter data or reset the sample passwords. It does not erase your saved workflow records.

## Testing students, scratch-card PDFs and Word questions

- **Students:** sign in as the school administrator and open Students. Search by name, email or admission number; filter by class/status. Click a name to open the profile or Edit to update it.
- **Scratch Cards:** enter a batch name and quantity, then click **Generate & Download PDF**. The printable PDF includes serials and PINs (10 cards per A4 page). Keep this original file: later **Unused Serials PDF** downloads contain serials only because PINs cannot be recovered from their stored hashes.
- **Word questions:** open Question Bank > Add Question. Choose Subject and Class Level, click **Download Word template**, edit it in Word and upload the saved .docx. You can also use [questions-template.docx](fixtures/questions-template.docx). Each extracted question automatically fills its own editable form. Review the text, options and answers, then click **Save all N questions**. A document containing 40 questions creates 40 separate question-bank records in one save. You can also type a question in the manual-entry fields and click **Save Question**.

The Word format uses one paragraph per line, for example:

    Question: What is 2 + 2?
    A. 3
    B. 4
    C. 5
    D. 6
    Answer: B
    Explanation: Adding two and two gives four.

    Question: The capital of Nigeria is _____.
    Answer: Abuja

Repeat "Question:" for each question. Multiple-choice questions need 2?4 options and a matching answer letter. Questions without options become fill-in questions (answers currently support up to 10 characters). Upload text only, up to 200 questions and 5 MB. Images, equations and embedded objects must be entered separately; documents containing them are rejected rather than silently losing those parts. Uploading previews the questions; it does not save them until you choose **Save all N questions** or **Save Question**.

## If something does not work

| Problem | What to do |
|---|---|
| The browser cannot open the page | Keep both terminals running and wait for frontend compilation. Use port **3001**. |
| The sample login fails on port 3000 | Open **http://127.0.0.1:3001**; Docker uses a different database. |
| Login fails on port 3001 | Run `python scripts/integration.py prepare` in another terminal, then retry in a fresh private window with the exact email and password above. |
| `No module named django` | Activate your project's Python environment. If dependencies are missing, run `python -m pip install -r backend/requirements.txt`, then retry. |
| `react-scripts` is missing | Run `npm --prefix frontend ci`, then start the frontend again. |
| Port 3001 or 8001 is already in use | Check for an already-running test server. Stop the old test server with Ctrl+C before restarting it. |

## Optional technical checks

The steps above are enough to start manual testing. The commands below are for checking readiness or investigating a connection problem. Run them from the repository root; use a third terminal while the two servers are running.

```powershell
# Prepare or repair the isolated fixtures, then verify login and profile responses.
python scripts/integration.py prepare

# Terminal 1: backend at http://127.0.0.1:8001
python scripts/integration.py serve

# Terminal 2: frontend at http://127.0.0.1:3001
npm --prefix frontend run start:integration

# Terminal 3: repeat the readiness check
python scripts/integration.py check
# With both servers running: verify the actual local HTTP connection
python scripts/integration.py live-check
```

Use a private browser window at **http://127.0.0.1:3001** to avoid cached branding or sessions from normal development. The frontend explicitly sends `X-School-Slug: qa-school` to the sandbox backend. No existing `.env` files are changed.

## Accounts and fixtures

All sandbox accounts use the local-only password **`PortalTest!2026`**. Use the normal sign-in page, or select Email on Parent Login.

| Account | Purpose |
|---|---|
| `school_admin@qa-school.test` | Import, configure school data, review results and collect fees |
| `teacher@qa-school.test` | Take attendance, enter grades and inspect timetable |
| `student@qa-school.test` | Linked child's attendance, results, fees and timetable |
| `parent@qa-school.test` | Linked child's results and fees |
| `unlinked_student@qa-school.test` | Same-school access-control negative case |

The same five accounts exist under `qa-other-school.test`. Their tenant slug is `qa-other-school`. To run the frontend for that school, stop it and restart with:

```powershell
$env:INTEGRATION_SCHOOL = 'qa-other-school'
npm --prefix frontend run start:integration
```

Remove that environment variable to return to the first school. Switching schools should use a fresh private browser session.

Generated files, ignored by Git:

- `.testing/portal.sqlite3`: persistent sandbox database.
- `.testing/accounts.json`: ten role accounts and account IDs.
- `.testing/fixtures.json`: school, term, class, subject, staff/student profile and account IDs.
- `.testing/readiness.json`: in-process preparation checks.
- `.testing/live-readiness.json`: live local HTTP checks, not a browser-test certification.

Fixtures include two schools, a current first term in the 2026/2027 session, JSS1 A, Mathematics, an assigned teacher, two students per school (only one linked to the parent), a Monday lesson and a 15,000 tuition schedule. Account IDs intentionally differ from profile IDs.

`prepare` is repeatable: it repairs the core fixture data and resets fixture passwords. It preserves workflow records and imported CSV rows. Reimporting a successful sample therefore exercises duplicate handling. The script refuses to seed any database other than `.testing/portal.sqlite3`.

## CSV samples

Use files in [fixtures](fixtures):

| File | Expected outcome |
|---|---|
| `staff-valid.csv` | One teacher imported through `/api/staff/bulk-import/` |
| `students-valid.csv` | One student imported through `/api/students/bulk-import/` |
| `staff-missing-role.csv` | Client blocks upload because `role` is missing |
| `staff-invalid-role.csv` | Backend reports a row error; no account created |
| `staff-duplicate.csv` | Backend reports duplicate email; no duplicate account |
| `staff-malformed.csv` | Client rejects the unclosed quoted field |

## Browser test run

Record actual results in [RUN_RESULTS.md](RUN_RESULTS.md). These are acceptance checks to run, not claims that they already pass.

| ID | Role and action | Expected result |
|---|---|---|
| AUTH-01 | Log in and refresh the page as each role | Session restores and the correct dashboard opens |
| CSV-01 | Admin uploads each CSV sample | Correct endpoint, validation and counts; no staff created as students |
| ATT-01 | Teacher opens today's JSS1 A register, marks absence with a remark, saves and reloads | Correct student's status and remark persist |
| ATT-02 | Teacher locks the saved register | Editing is disabled and later mutation is rejected |
| GRADE-01 | Teacher selects term/session/class/subject, saves test and exam scores as draft | Correct account IDs and scores persist; unpublished marks stay private |
| RESULT-01 | Teacher publishes; student opens results for the same term | Published scores appear for the correct student |
| RESULT-02 | Admin/student downloads PDF; admin downloads attendance PDF | Download succeeds with authentication and correct content |
| FEE-01 | Admin records a manual tuition payment | Balance updates and receipt belongs to the correct student |
| PARENT-01 | Parent opens linked child's result and fee pages | Detail links open the intended child and term |
| ACCESS-01 | Parent requests the unlinked student's details via UI and API | Access denied without another child's data |
| ACCESS-02 | Student requests another student's results, fees or attendance directly | Access denied without another student's data |
| ACCESS-03 | Reuse a school-A token against school-B fixture IDs/header | No school-B data exposed or modified |
| ROUTE-01 | Open each role's navigation links and refresh deep URLs | Correct page remains open; restricted routes redirect appropriately |
| ERROR-01 | Stop backend during a save/download; restore it and retry | Clear error, no false success, retry works without duplicate records |
| UI-01 | Repeat critical forms at mobile width and using keyboard | Usable labels, focus, controls, errors and scrolling |

For network evidence, inspect the browser Network panel. Distinguish student **profile IDs** (fees/enrollment/performance) from **account IDs** (attendance/gradebook/results). Record method, path, status and redacted response; never attach bearer tokens or passwords to issue reports.

## Boundaries of this sandbox

SQLite makes this preparation independent of Docker/PostgreSQL. Repeat database-sensitive workflows against disposable PostgreSQL before release. The readiness command uses Django's real middleware/authentication through an in-process HTTP client; it does not drive a browser.

Provider calls made with Python `requests` are blocked in these test settings, provider credentials are cleared, email uses a local memory backend, and Celery uses an in-memory broker without a worker. External notification delivery, parent SMS OTP, successful online payment, Cloudinary uploads and asynchronous analytics/promotion jobs are not end-to-end ready here. Test their failure states here; prepare provider sandboxes and a worker separately for successful delivery/payment/job checks. Do not deploy `config.settings.integration`.

Stop the two servers with Ctrl+C. The production and normal development databases are not used by these preparation commands.

## Latest testing steps

1. **Word import:** try [questions-40.docx](fixtures/questions-40.docx). In Question Bank > Add Question, choose Subject and Class Level and upload it. Check that 40 question forms appear, edit any answers if needed, and click **Save all 40 questions**. Use manual entry for single questions.
2. **Exam rules:** create or edit an exam, choose random selection, click Add Rule, and set a topic/difficulty and question count. Save, reopen Edit and check that the rules remain. A rule needs a whole number from 1 to 100.
3. **Notifications:** choose email, recipients, subject and message. In this sandbox, Send captures the message locally in Send History; it does not deliver to a real inbox or phone. Missing guardian contacts are reported as skipped. For Individual, choose the student whose guardian should receive it.
4. **PDF downloads:** attendance, debtors, scratch cards and import guides download as PDF. The Word question template remains a .docx so you can edit and upload it; staff/student import inputs still use CSV.
5. **Mobile:** narrow the browser to 360 px or use a phone. Open Menu to navigate. Question-bank filters can be expanded with Show filters. Wide tables and timetables scroll inside their containers, while forms and dialogs stack to fit the screen.

The test setup keeps external messaging and payment providers disabled. Successful local capture is labelled separately from external delivery.

## Platform owner and school registration

Use the [platform management guide](PLATFORM_GUIDE.md) for owner login, school signup, approval, administrator setup and subscription controls. The routing change is applied. The guide includes authenticator setup, platform staff permissions, audit records and a testing checklist. See also the [backup and recovery guide](RECOVERY_GUIDE.md).

## Paystack payments

See [Paystack setup and test checklist](PAYSTACK_GUIDE.md), [staging deployment checklist](STAGING_DEPLOYMENT_CHECKLIST.md), [Railway/Vercel deployment guide](RAILWAY_VERCEL_DEPLOYMENT_GUIDE.md), and [launch pricing assumptions](SUBSCRIPTION_PRICING.md).

## Plans and custom school designs

See [assign plans, colours and five portal layouts](PLANS_AND_DESIGNS.md). Open **Superadmin > Portal designs** to preview and save each school's appearance.

## User guides and mobile testing

The [complete user guide](../../docs/USER_GUIDE.md) covers owners, school administrators, staff, parents and students. Read guides at `/help` or **User guide**. PDF downloads are available only in **Superadmin > User guide**. Mobile checks now cover 320px, 390px and 768px forms, timetables and navigation across all five designs.


