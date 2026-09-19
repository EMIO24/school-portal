# Platform routing change - approved and applied

## Exact proposed change

Add only `"/api/platform/",` to `EXEMPT_PATH_PREFIXES` in `backend/tenants/middleware.py`. No existing school API prefix would be added, and no school-role permission would change.

## Reason

The platform owner manages schools that may be pending, suspended or not yet created. School registration must also work before an active school exists. Currently the tenant middleware can return 404 before either endpoint gets to enforce its own permissions.

## Endpoints affected

- `GET /api/platform/me/`: platform-owner permission.
- `GET/POST /api/platform/schools/`: platform-owner permission.
- `GET/PATCH/POST /api/platform/schools/<id>/`: platform-owner permission.
- `POST/PATCH /api/platform/schools/<id>/administrators/`: platform-owner permission, school-scoped administrator lookup.
- `POST /api/platform/register/`: public, throttled, always creates an inactive pending school and an ordinary school administrator. The client cannot grant owner permissions, approve itself or choose a paid plan.

## Verification

`backend/tenants/test_platform.py` tests denial of every management method to anonymous and school-admin callers, signup privilege injection, password validation, approval, suspension with an existing token, administrator scope, last-admin protection, owner profile access and signup throttling.

The single-prefix change is applied; the checks cover requests with nonexistent and suspended school headers. Also verify the owner dashboard and public signup in a browser without a selected school. Existing tenant-bound endpoints must remain blocked for inactive schools.

## Review outcome

The user explicitly approved completing this routing change. `/api/platform/` is now exempt from school lookup; the protected platform endpoints enforce authentication and owner/read-only permissions themselves. MFA verification is public only with a signed, expiring password-verified challenge. Registration remains public and creates inactive pending schools.

Regression tests confirm owner access with no schools and with absent/suspended school headers, rejection of school-admin management attempts, and continued blocking of inactive school APIs. Platform accounts additionally require two-factor authentication, and read-only staff cannot mutate school or platform records.
