l Launch Readiness Checklist

## Status
This checklist captures the remaining production-readiness work required before commercial launch. The project is structurally healthy and the major deployment blockers have been resolved, but the final launch gate is live validation, security hardening, and end-to-end quality assurance.

## 1. Security and secrets

### Must pass before launch
- [ ] Rotate `PLATFORM_MFA_KEY` if it was exposed in logs.
- [ ] Ensure no secret fragments, keys, or partial values are written to logs.
- [ ] Remove all debug `print(...)` statements from production code paths.
- [ ] Confirm no credentials are exposed through error responses or logs.
- [ ] Verify TLS is enforced for all production traffic.
- [ ] Confirm CORS allows only the real frontend origin(s).
- [ ] Confirm CSRF trusted origins include the deployed frontend domain.
- [ ] Verify cookie security settings are production-safe.
- [ ] Ensure all admin-only endpoints are protected and role-checked.
- [ ] Validate MFA enrollment flow is secure and recovery codes are handled safely.
- [ ] Verify session expiry and lockout behavior are working correctly.
- [ ] Confirm tenant isolation prevents cross-school data access.

## 2. Production QA smoke tests

### Authentication and MFA
- [ ] Superadmin login succeeds with valid credentials.
- [ ] Invalid password returns `401` and does not reveal account state.
- [ ] MFA challenge is returned for superadmin sign-in.
- [ ] QR code and setup secret render correctly.
- [ ] TOTP verification succeeds for a valid code.
- [ ] Invalid TOTP returns the correct error.
- [ ] Recovery codes work as expected during enrollment.
- [ ] Logout works correctly.
- [ ] Re-login after logout requires fresh authentication.
- [ ] Session restoration works for an authenticated user.

### Role-based access
- [ ] Superadmin can access all required admin functions.
- [ ] School admin has correct access privileges.
- [ ] Teacher access is restricted to assigned scope.
- [ ] Student access is restricted to own records.
- [ ] Parent access is restricted to assigned students.
- [ ] Cross-tenant access is denied.

### Core system functions
- [ ] School onboarding/tenant creation works.
- [ ] Academic records update correctly.
- [ ] Enrollment flow works.
- [ ] Attendance flow works.
- [ ] Gradebook flow works.
- [ ] Results generation works.
- [ ] CBT/exam flow works.
- [ ] Fees and payment flow works in the configured mode.
- [ ] Timetable management works.
- [ ] Notifications send correctly.
- [ ] Analytics data loads correctly.
- [ ] Promotion logic works correctly.

## 3. Cybersecurity validation

### Authentication and authorization
- [ ] Attempt login with incorrect credentials and confirm proper error handling.
- [ ] Attempt unauthorized API access without JWT and confirm rejection.
- [ ] Attempt a non-superadmin action from a restricted account and confirm denial.
- [ ] Confirm JWT tampering is rejected.
- [ ] Confirm tenant data cannot be accessed from another school.

### Input safety
- [ ] Attempt common SQL injection payloads in form fields and API inputs.
- [ ] Attempt XSS payloads in profile and content fields.
- [ ] Test invalid file upload behavior if file uploads are supported.
- [ ] Confirm validation is enforced for dates, IDs, and numeric inputs.

### Session and CSRF checks
- [ ] Verify cookies are Secure and HttpOnly where appropriate.
- [ ] Verify CSRF protection works for state-changing requests.
- [ ] Verify cross-origin requests from untrusted origins are rejected.
- [ ] Confirm rate limiting is active on authentication endpoints.

### Secret and log hygiene
- [ ] Confirm no API tokens, secrets, or partial keys appear in logs.
- [ ] Confirm production logs do not expose request bodies or sensitive metadata.
- [ ] Confirm error pages do not disclose internals or stack traces to end users.

## 4. Deployment and rollback validation

- [ ] Backend redeploy succeeds without breaking startup.
- [ ] Migrations run successfully on deploy.
- [ ] Database is reachable and queries work after deployment.
- [ ] Redis cache works after deploy.
- [ ] Static assets still load correctly after deploy.
- [ ] Frontend and backend connect correctly in production.
- [ ] Login works again after deploy.
- [ ] MFA still works after deploy.
- [ ] Rollback path is understood and documented.
- [ ] Backup and restore process is documented and tested.

## 5. Operational readiness

- [ ] Production monitoring is enabled.
- [ ] Error alerts are configured.
- [ ] Log aggregation is active.
- [ ] Backup procedure is defined and tested.
- [ ] Secret rotation procedure is documented.
- [ ] Support/admin access process is documented.
- [ ] Incident response plan exists.
- [ ] Post-launch monitoring checklist is defined.

## 6. Launch sign-off gate

The system is ready for commercial launch only when all of the following are true:
- [ ] No secrets are logged.
- [ ] MFA works in the live production frontend.
- [ ] Critical user flows pass in production.
- [ ] Tenant isolation and access control pass security tests.
- [ ] Red/amber issues are resolved or explicitly accepted with mitigation.
- [ ] Rollback and incident plan are in place.
- [ ] Launch owner signs off on live validation.

## 7. Recommended final launch decision

### Ready for internal pilot
- [ ] yes

### Ready for commercial use
- [ ] only after all required checks above pass in the live production environment.

## 8. Suggested execution order

1. Security cleanup and secret rotation
2. Live MFA login verification
3. Production smoke test
4. Cybersecurity validation
5. Rollback and operational checks
6. Final sign-off

---

This checklist should be used as the launch gate before enabling real commercial usage.
