# Railway Build Environment Fix

## Issue

The backend Docker build was failing during `collectstatic` because Django production settings were being imported before all required environment variables were available.

The failing check was in [backend/config/settings/production.py](../backend/config/settings/production.py):

- `ALLOWED_HOSTS` must be explicitly set
- `REDIS_URL` must be defined
- `FRONTEND_URL` must be present and use HTTPS
- `PAYSTACK_SECRET_KEY` must match the selected payment mode
- `PLATFORM_MFA_KEY` must be set

## Root cause

The build command in [backend/Dockerfile](../backend/Dockerfile) was running:

```dockerfile
RUN SECRET_KEY=dummy-build-secret \
    DATABASE_URL=sqlite:///dev-dummy.db \
    python manage.py collectstatic --noinput
```

This command only supplied a subset of the required values. As a result, Django raised:

```text
RuntimeError: Production requires explicit ALLOWED_HOSTS.
```

## Fix applied

The build step was updated to supply the minimum production-safe placeholder values needed for Django to import the production settings during static collection.

The build command now includes placeholders for:

- `ALLOWED_HOSTS`
- `REDIS_URL`
- `FRONTEND_URL`
- `CORS_ALLOWED_ORIGINS`
- `PAYSTACK_MODE`
- `PAYSTACK_SECRET_KEY`
- `PLATFORM_MFA_KEY`

This allows the container image to build successfully while preserving the production validation checks.

## Security note

These values are only placeholders used during the build stage. They are not real production credentials.

The important security requirement is that real runtime values must still be configured in Railway for the deployed service. If real secrets are missing in the runtime environment, the app may still start with incomplete or non-production settings.

## Recommendation

- Keep real secrets in Railway environment variables, not in Dockerfile source.
- Ensure the same variables are present in the runtime service environment after deployment.
- Treat any build-time placeholder values as a temporary compatibility measure only.
- Prefer validating that the service is using real environment variables at runtime before production release.

## Verification

This fix was verified by the Docker build log showing:

```text
154 static files copied to '/app/staticfiles', 736 post-processed.
```

This confirms the build-time `collectstatic` step completed successfully.
