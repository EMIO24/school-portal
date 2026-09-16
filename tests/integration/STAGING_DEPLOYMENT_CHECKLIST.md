# Staging deployment checklist

Use this checklist before accepting real school records or live payments. Staging must use a separate database, separate frontend URL and Paystack test mode.

## 1. Create the staging environment

Set backend variables in the hosting secret manager, not in source files:

```text
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<unique staging secret, 50+ chars>
PLATFORM_MFA_KEY=<stable Fernet key>
DATABASE_URL=<staging PostgreSQL URL with SSL>
REDIS_URL=<staging Redis rediss:// URL>
ALLOWED_HOSTS=<staging backend host>
FRONTEND_URL=<staging frontend HTTPS URL>
CORS_ALLOWED_ORIGINS=<staging frontend HTTPS URL>
PAYSTACK_MODE=test
PAYSTACK_SECRET_KEY=<Paystack test secret>
DEPLOYMENT_CHECK_ARGS=--allow-test-payments
TERMII_API_KEY=<test/sandbox key if available>
BREVO_API_KEY=<test/sandbox key if available>
DEFAULT_FROM_EMAIL=<verified staging sender>
RUN_MIGRATIONS=true
```

Worker and beat services should use the same secrets but `RUN_MIGRATIONS=false`. Run exactly one beat instance.

## 2. Run release checks before pushing

From the repository root:

```powershell
.venv-release\Scripts\python backend\manage.py test accounts academics enrollment tenants fees cbt gradebook results attendance timetable analytics promotion notifications --settings=config.settings.test --noinput
.venv-release\Scripts\python scripts\audit_readiness.py
.venv-release\Scripts\pip-audit -r backend\requirements.txt
npm --prefix frontend test -- --watchAll=false --runInBand --silent --forceExit
npm --prefix frontend run build
npm --prefix frontend audit --omit=dev
```

The CRA test runner currently needs `--forceExit` after passing because it keeps an open handle in the legacy test environment.

## 3. Deploy staging

Deploy backend web, worker and beat. Startup should run `deployment_check`, Django deploy checks and migrations before the web process starts. A failed deployment check means a required secret or production safety setting is missing.

Deploy frontend with these variables:

```text
REACT_APP_API_URL=<staging backend HTTPS URL>
REACT_APP_PAYSTACK_PUBLIC_KEY=<Paystack test public key>
REACT_APP_SCHOOL_SLUG=<optional default school slug>
```

## 4. Verify workflows in staging

- Platform owner can sign in with MFA and manage schools even when no school is selected.
- School registration stays pending until the owner approves it and assigns the first school admin.
- Suspended schools cannot operate as active schools, while platform owner management still works.
- School admin can add students, staff, class arms, subjects, timetable periods and fees.
- Teacher can only work on assigned class/subject data.
- Student/parent cannot cross into another student's records.
- CBT exam cannot start early, after expiry, or for unassigned students.
- Imported DOCX questions create the expected number of editable questions.
- Scratch cards, receipts, attendance and debtors downloads produce PDF files.
- Mobile views fit at 390px without horizontal scrolling.

## 5. Verify payments without live money

Follow `tests/integration/PAYSTACK_GUIDE.md` in Paystack test mode:

- Connect a distinct test subaccount for each school.
- Pay a portal subscription and confirm plan/expiry changes once.
- Pay school fees and confirm receipt PDF, outstanding balance and idempotent refresh.
- Trigger failed/pending payment states and confirm no fee credit is applied.
- Use owner verification/retry only against the same Paystack reference.

Do not switch a real school to test mode. Use staging data only.

## 6. Prove recovery

Follow `tests/integration/RECOVERY_GUIDE.md` against the staging PostgreSQL database:

- Run `backup_portal` to a new backup directory.
- Restore into a new `portal_restore_*` database.
- Verify school count, users, migrations, representative uploaded files and owner MFA login.
- Record the restore date, database name and backup location.

## 7. Live production gate

Only move to live production after staging passes with no critical defects. For live production, change Paystack to live mode, reconnect each school's live subaccount, register the live webhook URL and complete a fresh backup/restore drill against the production hosting stack before onboarding real schools.
