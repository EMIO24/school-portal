# Postman Test Suite

Files:

- `school-portal-api-tests.postman_collection.json`
- `school-portal-local.postman_environment.json`

What this collection handles automatically:

- stores admin, teacher, and student JWTs in collection variables
- generates run-specific teacher and student emails so reruns do not collide
- persists shared IDs like `session_id`, `term_id`, `student_user_id`, and `exam_id`
- uses Postman's cookie jar automatically if any endpoint sets cookies
- avoids session/cookie coupling by authenticating all protected requests with bearer tokens

How to run:

1. Import the collection and environment into Postman.
2. Select the `School Portal Local` environment.
3. Set `base_url`, `school_slug`, `admin_email`, and `admin_pass` if your local values differ.
4. Run the full collection in Collection Runner.

Optional Newman command:

```bash
newman run postman/school-portal-api-tests.postman_collection.json \
  -e postman/school-portal-local.postman_environment.json
```

Notes:

- The parent dashboard/children endpoints are not included because they require a pre-linked parent account.
- External integrations are treated as acceptable when they return their expected non-local statuses:
  - Paystack initiate: `200` or `502`
  - Notifications send: `200`, `201`, `207`, or `500`
  - Analytics transcript/trends endpoints accept `404` when no extra data exists yet.
