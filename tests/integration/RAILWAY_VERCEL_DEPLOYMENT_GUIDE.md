# Railway and Vercel deployment guide

This guide is for the startup deployment path: Railway Hobby for the backend and Vercel Free for the frontend. Use staging first, then switch to live production only after payment, SMS/email and backup restore checks pass.

## What you need before deployment

- GitHub repository with the latest `Update` branch pushed.
- Railway account on Hobby plan.
- Vercel account. Free is fine for the React frontend while usage stays within the free limits and the project is eligible for that plan.
- Paystack account. Use test mode for staging; use live mode only after business activation and settlement checks.
- Termii account for SMS/OTP.
- Brevo account for email. The free plan is enough at the beginning if you stay within its daily limit.
- Cloudinary account for media uploads. The free plan is enough at the beginning if image/document usage is small.
- One domain name, for example `myschoolportal.com`, if you want a professional public URL.

## Recommended domain setup

Use subdomains like this:

```text
api.yourdomain.com      -> Railway backend
portal.yourdomain.com   -> Vercel frontend
```

You can also use provider URLs at first:

```text
https://your-app.up.railway.app
https://your-app.vercel.app
```

Provider URLs are cheaper to start with, but a custom domain looks more professional for schools.

## What domain reserve means

A domain reserve is money you set aside every month so the yearly domain renewal does not surprise you later.

Example:

```text
Domain renewal estimate: ₦30,000 per year
Monthly reserve: ₦30,000 / 12 = ₦2,500 per month
Term reserve: ₦2,500 x 3 = ₦7,500 per term
```

It is not a monthly bill from the domain company. It is your own savings line. If the domain costs ₦40,000/year, reserve about ₦3,400/month. If you use a free Railway/Vercel URL for staging, domain reserve can be ₦0 until you buy a domain.

## Railway backend deployment

Create one Railway project and connect it to GitHub.

Add these services:

```text
PostgreSQL
Redis
backend-web
backend-worker
backend-beat
```

All three backend services should use the same repository and backend source folder.

### Backend service settings

For `backend-web`:

```text
Root directory: backend
Start command: bash entrypoint.sh
```

For `backend-worker`:

```text
Root directory: backend
Start command: celery -A config worker --loglevel=info
```

For `backend-beat`:

```text
Root directory: backend
Start command: celery -A config beat --loglevel=info
```

Run only one beat service. Beat is the scheduler for background jobs.

## Railway backend environment variables

Set these in Railway Variables for the backend services.

For staging with Paystack test mode:

```text
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<generate a strong 50+ character secret>
PLATFORM_MFA_KEY=<generate a stable Fernet key>
DATABASE_URL=<Railway PostgreSQL private URL>
REDIS_URL=<Railway Redis private URL, preferably rediss://>
ALLOWED_HOSTS=<your Railway backend domain or api.yourdomain.com>
FRONTEND_URL=<your Vercel frontend URL>
CORS_ALLOWED_ORIGINS=<your Vercel frontend URL>
PAYSTACK_MODE=test
PAYSTACK_SECRET_KEY=<Paystack test secret key>
DEPLOYMENT_CHECK_ARGS=--allow-test-payments
TERMII_API_KEY=<Termii API key>
BREVO_API_KEY=<Brevo API key>
DEFAULT_FROM_EMAIL=<verified sender email>
RUN_MIGRATIONS=true
```

For `backend-worker` and `backend-beat`, use the same variables but set:

```text
RUN_MIGRATIONS=false
```

Only the web service should run migrations.

For live production, change:

```text
PAYSTACK_MODE=live
PAYSTACK_SECRET_KEY=<Paystack live secret key>
DEPLOYMENT_CHECK_ARGS=
```

Do not use Paystack live mode until staging payment tests pass.

## Generate keys

Generate `SECRET_KEY` with Python:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Generate `PLATFORM_MFA_KEY` with Python:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep `PLATFORM_MFA_KEY` stable. If you change it later, already enrolled platform-owner authenticator secrets may stop working.

## Vercel frontend deployment

Create a Vercel project from the same GitHub repository.

Use these settings:

```text
Root directory: frontend
Build command: npm run build
Output directory: build
Install command: npm ci
```

Set these Vercel environment variables:

```text
REACT_APP_API_URL=<Railway backend HTTPS URL>
REACT_APP_PAYSTACK_PUBLIC_KEY=<Paystack public key for the same mode>
REACT_APP_SCHOOL_SLUG=<optional default school slug>
```

For staging, use Paystack test public key. For production, use Paystack live public key.

## Paystack setup

In staging:

- Use Paystack test mode.
- Create test subaccounts for schools.
- Connect each school subaccount in the platform owner Payments page.
- Pay a portal subscription in test mode.
- Pay a student fee in test mode.
- Confirm failed/pending payments do not create receipts.
- Confirm refresh/retry does not create duplicate receipts.

In production:

- Complete Paystack business activation.
- Create/connect live subaccounts for each school.
- Register the live webhook URL:

```text
https://api.yourdomain.com/api/platform/paystack/webhook/
```

If using Railway URL instead of a custom domain, use:

```text
https://your-railway-backend.up.railway.app/api/platform/paystack/webhook/
```

## Post-deployment checks

After Railway and Vercel deploy successfully:

- Open the frontend URL.
- Sign in as platform owner.
- Set up/verify MFA.
- Create or approve a school.
- Assign the school administrator.
- Sign in as school admin.
- Add class arms, subjects, students and staff.
- Add timetable periods and entries.
- Import DOCX questions and confirm question forms are filled.
- Generate scratch cards and confirm PDF download.
- Test school fee payment in Paystack test mode.
- Test portal subscription in Paystack test mode.
- Check mobile layout at about 390px width.

## Backup and restore check

Before onboarding real schools, run a restore drill using the staging database.

```powershell
python backend/manage.py backup_portal --output .backups/staging-drill
python backend/manage.py restore_portal --backup .backups/staging-drill --database portal_restore_staging --media-destination .restores/staging-media
```

The restore database name must start with `portal_restore_`. Never restore over the live database.

## Startup cost guide for 100 students

With Railway Hobby and Vercel Free, an early 100-student school should be much cheaper than a full production Pro setup.

Estimated monthly startup cost:

```text
Railway Hobby: about $5/month
Vercel Free: ₦0 while eligible and within limits
Brevo Free: ₦0 initially
Cloudinary Free: ₦0 initially
Domain reserve: ₦0 if using provider URLs; about ₦2,500-₦4,000/month if saving for yearly domain renewal
SMS reserve: depends on Termii usage; start with ₦1,000-₦5,000/month per 100 students
```

Estimated cost per 3-month term:

```text
Without custom domain: roughly ₦25,000-₦35,000 per 100-student school
With domain reserve: roughly ₦32,000-₦50,000 per 100-student school
```

This is cost, not selling price. Your selling price should include support time, onboarding, training, risk buffer, payment reconciliation work and profit.

Suggested starting prices:

```text
Basic: ₦30,000-₦50,000 per term
Premium: ₦60,000-₦100,000 per term
```

As more schools join, the fixed hosting cost is shared across all schools, so the cost per school drops.
