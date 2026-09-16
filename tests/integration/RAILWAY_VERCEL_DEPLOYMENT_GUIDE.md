# Railway and Vercel deployment guide

This is a step-by-step guide for deploying the school portal with:

```text
Backend: Railway Hobby
Frontend: Vercel Free
Database: Railway PostgreSQL
Cache/queue broker: Railway Redis
Payments: Paystack
SMS: Termii
Email: Brevo
Media: Cloudinary
```

Use staging first. Do not accept real school records or live payments until staging has passed.

## 1. What you need before you start

Create or prepare these accounts:

- GitHub account with this repository pushed.
- Railway account on Hobby plan.
- Vercel account.
- Paystack account.
- Termii account.
- Brevo account.
- Cloudinary account.
- Optional custom domain, for example `yourdomain.com`.

You can deploy without a custom domain first by using Railway and Vercel URLs.

## 2. Confirm the branch on GitHub

The current deployment branch is:

```text
Update
```

GitHub repository:

```text
https://github.com/EMIO24/school-portal
```

If you want to deploy from `main`, merge the `Update` branch into `main` first. If you are still testing, deploy directly from `Update`.

## 3. Generate backend secrets

Open PowerShell in the project folder.

Generate `SECRET_KEY`:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Copy the output somewhere private.

Generate `PLATFORM_MFA_KEY`:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output somewhere private.

Do not lose `PLATFORM_MFA_KEY`. It protects platform-owner authenticator secrets. If you change it later, existing owner MFA setup can stop working.

## 4. Create the Railway project

1. Go to Railway.
2. Click **New Project**.
3. Choose **Deploy from GitHub repo**.
4. Select `EMIO24/school-portal`.
5. Select the branch you want to deploy, usually `Update` for staging.
6. Railway will create a service. Rename it to:

```text
backend-web
```

## 5. Add PostgreSQL on Railway

1. Inside the Railway project, click **New**.
2. Choose **Database**.
3. Choose **PostgreSQL**.
4. Wait for it to finish provisioning.
5. Open the PostgreSQL service.
6. Go to **Variables**.
7. Copy the private database URL if Railway exposes one. Use the private/internal URL when possible.

You will use it as:

```text
DATABASE_URL=<Railway PostgreSQL URL>
```

## 6. Add Redis on Railway

1. Inside the same Railway project, click **New**.
2. Choose **Database** or template.
3. Choose **Redis**.
4. Wait for it to finish provisioning.
5. Open the Redis service.
6. Go to **Variables**.
7. Copy the Redis URL.

You will use it as:

```text
REDIS_URL=<Railway Redis URL>
```

Prefer a TLS Redis URL if available, usually starting with:

```text
rediss://
```

## 7. Configure `backend-web` on Railway

Open the `backend-web` service.

Go to **Settings**.

Set the root directory:

```text
backend
```

Set the start command:

```bash
bash entrypoint.sh
```

If Railway asks for build settings, keep the normal Docker build. This repo includes `backend/Dockerfile`.

## 8. Add backend-web variables

Open `backend-web` then go to **Variables**.

For staging, add:

```text
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<your generated SECRET_KEY>
PLATFORM_MFA_KEY=<your generated PLATFORM_MFA_KEY>
DATABASE_URL=<Railway PostgreSQL URL>
REDIS_URL=<Railway Redis URL>
ALLOWED_HOSTS=<temporary Railway backend domain without https://>
FRONTEND_URL=<temporary Vercel frontend URL, add later if unknown>
CORS_ALLOWED_ORIGINS=<temporary Vercel frontend URL, add later if unknown>
PAYSTACK_MODE=test
PAYSTACK_SECRET_KEY=<Paystack test secret key>
DEPLOYMENT_CHECK_ARGS=--allow-test-payments
TERMII_API_KEY=<Termii API key>
BREVO_API_KEY=<Brevo API key>
DEFAULT_FROM_EMAIL=<verified sender email>
RUN_MIGRATIONS=true
```

At this point you may not know the Vercel URL yet. If you do not know it, put a temporary value like:

```text
FRONTEND_URL=https://example.com
CORS_ALLOWED_ORIGINS=https://example.com
```

You will replace it after Vercel deploys.

## 9. Generate a Railway backend URL

1. Open `backend-web`.
2. Go to **Settings**.
3. Find **Networking** or **Domains**.
4. Click **Generate Domain**.
5. Railway gives you a URL like:

```text
https://school-portal-production.up.railway.app
```

Copy the host only for `ALLOWED_HOSTS`:

```text
school-portal-production.up.railway.app
```

Then update `backend-web` variables:

```text
ALLOWED_HOSTS=school-portal-production.up.railway.app
```

Redeploy `backend-web` after changing variables.

## 10. Confirm backend health

Open this URL in your browser:

```text
https://YOUR-RAILWAY-BACKEND-DOMAIN/health/
```

Expected result:

```json
{"status":"ok","version":"1.0"}
```

If it fails, open Railway logs for `backend-web` and check the deployment error. Common causes are missing variables, wrong `DATABASE_URL`, wrong `REDIS_URL`, or `ALLOWED_HOSTS` not matching the Railway domain.

## 11. Create the Celery worker on Railway

1. Inside the same Railway project, click **New**.
2. Choose **GitHub repo**.
3. Select the same repository and branch.
4. Rename this service to:

```text
backend-worker
```

Set root directory:

```text
backend
```

Set start command:

```bash
celery -A config worker --loglevel=info
```

Copy all variables from `backend-web`, but change:

```text
RUN_MIGRATIONS=false
```

Deploy it.

## 12. Create the Celery beat scheduler on Railway

1. Inside the same Railway project, click **New**.
2. Choose **GitHub repo**.
3. Select the same repository and branch.
4. Rename this service to:

```text
backend-beat
```

Set root directory:

```text
backend
```

Set start command:

```bash
celery -A config beat --loglevel=info
```

Copy all variables from `backend-web`, but change:

```text
RUN_MIGRATIONS=false
```

Deploy it.

Run only one `backend-beat` service. Two beat services can duplicate scheduled jobs.

## 13. Deploy frontend on Vercel

1. Go to Vercel.
2. Click **Add New**.
3. Choose **Project**.
4. Import the GitHub repository:

```text
EMIO24/school-portal
```

5. Choose the same branch you deployed on Railway, usually:

```text
Update
```

6. In project settings, set:

```text
Framework Preset: Create React App
Root Directory: frontend
Build Command: npm run build
Install Command: npm ci
Output Directory: build
```

7. Add environment variables:

```text
REACT_APP_API_URL=https://YOUR-RAILWAY-BACKEND-DOMAIN
REACT_APP_PAYSTACK_PUBLIC_KEY=<Paystack test public key>
REACT_APP_SCHOOL_SLUG=qa-school
```

`REACT_APP_SCHOOL_SLUG` is optional, but useful during testing.

8. Click **Deploy**.

## 14. Copy the Vercel URL back to Railway

After Vercel deploys, copy the frontend URL. It will look like:

```text
https://school-portal-xxxx.vercel.app
```

Go back to Railway `backend-web`, `backend-worker`, and `backend-beat` variables.

Set:

```text
FRONTEND_URL=https://school-portal-xxxx.vercel.app
CORS_ALLOWED_ORIGINS=https://school-portal-xxxx.vercel.app
```

Redeploy all backend services after changing those variables.

## 15. Test frontend to backend connection

Open the Vercel URL.

Try:

```text
/platform/login
```

If login page opens, frontend is running.

If the app cannot reach the backend:

- Check `REACT_APP_API_URL` in Vercel.
- Check `FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` in Railway.
- Check Railway backend logs.
- Confirm backend `/health/` still works.

## 16. Set up the first platform owner

The backend supports owner/platform management. If you use the automatic bootstrap environment variables, add these only to `backend-web` temporarily:

```text
DJANGO_SUPERUSER_EMAIL=<your owner email>
DJANGO_SUPERUSER_PASSWORD=<temporary strong password>
```

Redeploy `backend-web` once. After the owner account exists, remove these variables and redeploy again.

Then open:

```text
https://YOUR-VERCEL-FRONTEND/platform/login
```

Sign in and complete MFA setup.

Do not share the MFA setup key or recovery codes.

## 17. Create or approve a school

From the platform owner panel:

1. Open the school management page.
2. Create a school or approve a submitted school registration.
3. Assign the first school administrator.
4. Give the administrator their login link and temporary password privately.
5. The administrator should sign in and change the temporary password.

## 18. Paystack test mode setup

In Paystack dashboard:

1. Switch to **Test Mode**.
2. Copy test secret key to Railway:

```text
PAYSTACK_SECRET_KEY=sk_test_...
PAYSTACK_MODE=test
```

3. Copy test public key to Vercel:

```text
REACT_APP_PAYSTACK_PUBLIC_KEY=pk_test_...
```

4. Create a test subaccount for each school.
5. In the platform owner Payments page, connect that school to its test subaccount.
6. Test portal subscription payment.
7. Test school fee payment.
8. Confirm receipts are created only after backend verification.

## 19. Paystack webhook setup

In Paystack test mode, add this webhook URL:

```text
https://YOUR-RAILWAY-BACKEND-DOMAIN/api/platform/paystack/webhook/
```

If you later use a custom backend domain, use:

```text
https://api.yourdomain.com/api/platform/paystack/webhook/
```

For live production, add the webhook in Paystack live mode too.

## 20. Optional custom domain setup

You can skip this at first and use Railway/Vercel URLs.

If you have a domain, recommended setup:

```text
api.yourdomain.com      -> Railway backend
portal.yourdomain.com   -> Vercel frontend
```

### Backend custom domain on Railway

1. Open `backend-web` in Railway.
2. Go to **Settings** then **Domains**.
3. Add custom domain:

```text
api.yourdomain.com
```

4. Railway will show DNS records to add at your domain provider.
5. Go to your domain provider DNS page.
6. Add the DNS record Railway gives you.
7. Wait for Railway to verify it.
8. Update Railway variables:

```text
ALLOWED_HOSTS=api.yourdomain.com
```

If you also want to keep the Railway URL working, include both hosts separated by comma:

```text
ALLOWED_HOSTS=api.yourdomain.com,school-portal-production.up.railway.app
```

### Frontend custom domain on Vercel

1. Open the Vercel project.
2. Go to **Settings** then **Domains**.
3. Add:

```text
portal.yourdomain.com
```

4. Vercel will show DNS records.
5. Add those records at your domain provider.
6. Wait for Vercel to verify it.
7. Update Vercel environment variable:

```text
REACT_APP_API_URL=https://api.yourdomain.com
```

8. Update Railway variables:

```text
FRONTEND_URL=https://portal.yourdomain.com
CORS_ALLOWED_ORIGINS=https://portal.yourdomain.com
```

9. Redeploy Vercel and Railway.

## 21. What domain reserve means

A domain reserve is money you set aside every month so the yearly domain renewal does not surprise you later.

Example:

```text
Domain renewal estimate: ₦30,000 per year
Monthly reserve: ₦30,000 / 12 = ₦2,500 per month
Term reserve: ₦2,500 x 3 = ₦7,500 per term
```

It is not a monthly bill from the domain company. It is your own savings line.

If the domain costs ₦40,000/year:

```text
₦40,000 / 12 = about ₦3,400/month
```

If you use free Railway and Vercel URLs, domain reserve is ₦0 until you buy a domain.

## 22. Required staging tests before live use

Run these before using real school records:

- Platform owner can log in with MFA.
- Owner can create/approve/suspend schools.
- School admin can add students, staff, subjects, class arms and timetable periods.
- Teacher can only access assigned class/subject records.
- Student cannot access another student's records.
- Parent can only access linked children.
- DOCX question import creates the correct number of questions.
- CBT exams cannot start early, after expiry or for unassigned students.
- Scratch cards download as PDF.
- Receipts download as PDF.
- Attendance/debtors exports download as PDF.
- Paystack test payment verifies through backend before receipt/renewal.
- Failed or pending payment does not create a receipt.
- Mobile layout works around 390px width.

## 23. Backup and restore drill

Before onboarding real schools, run a restore drill using staging data.

From a machine that has access to the staging database and PostgreSQL tools:

```powershell
python backend/manage.py backup_portal --output .backups/staging-drill
python backend/manage.py restore_portal --backup .backups/staging-drill --database portal_restore_staging --media-destination .restores/staging-media
```

The restore database name must start with:

```text
portal_restore_
```

Never restore over the live database.

## 24. Switching from staging to live production

After staging passes:

1. In Paystack, complete business activation.
2. Create live school subaccounts.
3. Change Railway variables:

```text
PAYSTACK_MODE=live
PAYSTACK_SECRET_KEY=sk_live_...
DEPLOYMENT_CHECK_ARGS=
```

4. Change Vercel variable:

```text
REACT_APP_PAYSTACK_PUBLIC_KEY=pk_live_...
```

5. Add live Paystack webhook:

```text
https://api.yourdomain.com/api/platform/paystack/webhook/
```

6. Redeploy Railway and Vercel.
7. Run one controlled live transaction with a small amount.
8. Confirm receipt and settlement.

## 25. Startup cost guide for 100 students

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

## 26. Common deployment problems

### Backend says DisallowedHost

Fix `ALLOWED_HOSTS` in Railway. It must contain the backend host without `https://`.

### Frontend cannot call backend

Check:

```text
Vercel REACT_APP_API_URL
Railway FRONTEND_URL
Railway CORS_ALLOWED_ORIGINS
```

Then redeploy both.

### Deployment check fails because Paystack is test mode

For staging, set:

```text
DEPLOYMENT_CHECK_ARGS=--allow-test-payments
```

For production, use live Paystack keys instead.

### Owner MFA stops working

Check whether `PLATFORM_MFA_KEY` changed. It must stay stable.

### Worker or beat fails

Confirm Redis is reachable and `REDIS_URL` is set on worker and beat.

### Scheduled jobs duplicate

Make sure only one `backend-beat` service is running.
