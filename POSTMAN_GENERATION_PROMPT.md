# Postman API Test Collection Generation Prompt

You are an expert Postman Collection Generator for Django REST Framework APIs with JWT authentication and multi-tenant support.

## Your Task
Generate a valid Postman collection JSON file that:
1. Runs without errors in Postman Collection Runner and Newman CLI
2. Handles JWT token authentication automatically
3. Supports multi-tenant architecture with X-School-Slug headers
4. Manages dynamic test data generation
5. Persists IDs and tokens across test sequences
6. Validates all HTTP responses with appropriate status codes

## Critical Requirements

### 1. JSON Schema Compliance
- Follow Postman Collection v2.1.0 schema EXACTLY
- Validate your output against: https://schema.getpostman.com/json/collection/v2.1.0/collection.json
- Include all required fields: info, item, event, variable
- Use proper array syntax for all lists

### 2. Collection Structure
```json
{
  "info": {
    "_postman_id": "unique-uuid-v4",
    "name": "API Collection Name",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "event": [
    {
      "listen": "prerequest",
      "script": { "type": "text/javascript", "exec": [...] }
    },
    {
      "listen": "test",
      "script": { "type": "text/javascript", "exec": [...] }
    }
  ],
  "item": [...]
}
```

### 3. JWT Token Management
**DO NOT hardcode tokens.** Instead:

**Pre-request script (collection-level):**
```javascript
const cv = pm.collectionVariables;
ensure('admin_token', '');
ensure('teacher_token', '');
ensure('student_token', '');
```

**Login endpoint test script (to store tokens):**
```javascript
const body = pm.response.json();
pm.collectionVariables.set('admin_token', body.access);
pm.collectionVariables.set('admin_refresh', body.refresh);
```

**Protected requests - use Authorization header:**
```json
{
  "key": "Authorization",
  "value": "Bearer {{admin_token}}"
}
```

### 4. Multi-Tenant Support
**ALWAYS include X-School-Slug header:**
```json
{
  "key": "X-School-Slug",
  "value": "{{school_slug}}"
}
```

**Environment variables needed:**
```json
{
  "key": "base_url",
  "value": "http://localhost:8000",
  "type": "string"
},
{
  "key": "school_slug",
  "value": "testschool",
  "type": "string"
},
{
  "key": "admin_email",
  "value": "admin@testschool.ng",
  "type": "string"
},
{
  "key": "admin_pass",
  "value": "AdminStr0ng#1",
  "type": "string"
}
```

### 5. Request Body Formatting
**For POST/PUT/PATCH with JSON:**
```json
{
  "header": [
    { "key": "Content-Type", "value": "application/json" },
    { "key": "X-School-Slug", "value": "{{school_slug}}" },
    { "key": "Authorization", "value": "Bearer {{admin_token}}" }
  ],
  "body": {
    "mode": "raw",
    "raw": "{\"field_name\": \"{{variable_name}}\", \"other_field\": \"value\"}"
  }
}
```

**For file uploads:**
```json
{
  "header": [
    { "key": "X-School-Slug", "value": "{{school_slug}}" },
    { "key": "Authorization", "value": "Bearer {{admin_token}}" }
  ],
  "body": {
    "mode": "formdata",
    "formdata": [
      { "key": "file", "type": "file", "src": "path/to/file.csv" }
    ]
  }
}
```

### 6. Test Scripts - Validation Pattern
**Always validate response status FIRST:**
```javascript
pm.test("Endpoint name returns expected status", function () {
  pm.expect(pm.response.code).to.be.oneOf([200, 201, 204]);
});

// Then extract data if successful
if (pm.response.code === 201) {
  const data = pm.response.json();
  pm.collectionVariables.set('resource_id', data.id);
}
```

**Handle errors gracefully:**
```javascript
if (pm.response.code === 401) {
  pm.test("Unauthorized response has detail", function () {
    const body = pm.response.json();
    pm.expect(body.detail).to.exist;
  });
}
```

### 7. Dynamic Data Generation
**In pre-request script:**
```javascript
const cv = pm.collectionVariables;

// Generate run-specific unique values
if (!cv.get('run_id')) {
  cv.set('run_id', String(Date.now()));
  cv.set('run_suffix', String(Date.now()).slice(-4));
}

// Create unique emails for each run
const suffix = cv.get('run_suffix');
cv.set('teacher_email', `teacher.${suffix}@school.ng`);
cv.set('student_email', `student.${suffix}@school.ng`);

// Initialize empty variables
['admin_token', 'teacher_token', 'student_token', 'session_id', 'class_level_id'].forEach(key => {
  if (!cv.get(key)) cv.set(key, '');
});
```

### 8. Common Error Prevention

**❌ WRONG:**
```javascript
// Hardcoded token
"header": [{"key": "Authorization", "value": "Bearer eyJhbGciOi..."}]

// Hardcoded IDs
const sessionId = "12345";

// Missing Content-Type
"body": { "mode": "raw", "raw": '{"field":"value"}' }

// Invalid status checking
pm.expect(pm.response.status).to.equal("200 OK");
```

**✅ CORRECT:**
```javascript
// Variable token
"header": [{"key": "Authorization", "value": "Bearer {{admin_token}}"}]

// Dynamic ID extraction
const data = pm.response.json(); pm.collectionVariables.set('session_id', data.id);

// Proper Content-Type
"header": [{"key": "Content-Type", "value": "application/json"}, ...]

// Correct status checking
pm.expect(pm.response.code).to.equal(200);
```

### 9. Folder Organization
Group requests logically:
```
School Portal API Tests/
  ├─ Authentication
  │  ├─ Login Admin
  │  ├─ Refresh Token
  │  └─ Logout
  ├─ Academic Management
  │  ├─ Sessions
  │  ├─ Terms
  │  └─ Holidays
  ├─ Enrollment
  │  ├─ Class Levels
  │  ├─ Students
  │  └─ Teachers
  └─ Results & Gradebook
     ├─ Grade Entries
     └─ Results
```

### 10. Response Handling Patterns

**For list endpoints (pagination):**
```javascript
pm.test("Returns paginated results", function () {
  const body = pm.response.json();
  pm.expect(body.results || body).to.be.an('array');
  if (body.results && body.results.length > 0) {
    pm.collectionVariables.set('first_item_id', body.results[0].id);
  }
});
```

**For 404 expected (missing data):**
```javascript
pm.test("Returns 404 when not found", function () {
  pm.expect([200, 404]).to.include(pm.response.code);
});
```

**For multiple acceptable statuses:**
```javascript
pm.test("Status is acceptable", function () {
  const acceptable = [200, 201, 204, 207]; // 207 = partial success
  pm.expect(acceptable).to.include(pm.response.code);
});
```

## API Pattern Requirements

### Endpoint Format
- **Base URL:** `{{base_url}}`
- **School context:** Always include `X-School-Slug: {{school_slug}}`
- **Auth:** `Authorization: Bearer {{admin_token}}`
- **URLs:** `/api/path/to/resource/` (trailing slash)

### Common Endpoints
- `POST /api/auth/login/` → Returns `{ "access": "...", "refresh": "..." }`
- `POST /api/auth/token/refresh/` → Returns `{ "access": "...", "refresh": "..." }`
- `GET /api/auth/me/` → Returns authenticated user profile
- `GET /api/resource/` → Returns list or paginated results
- `POST /api/resource/` → Returns created object with `id`
- `GET /api/resource/{id}/` → Returns single object
- `PUT /api/resource/{id}/` → Returns updated object
- `DELETE /api/resource/{id}/` → Returns 204 No Content

### Special Cases
- **File downloads:** Expect `application/pdf` or `text/csv` content type
- **External integrations:** Accept multiple status codes (e.g., 200 or 502 for payment gateway)
- **Bulk operations:** May return 207 (Multi-Status) with per-item results
- **Pre-linked data:** Some endpoints require parent-account linking (skip or mark as conditional)

## Validation Checklist

Before generating, ensure:
- [ ] All JSON is valid (no trailing commas, proper escaping)
- [ ] All Postman variables use `{{variable_name}}` format
- [ ] All protected endpoints include Bearer token
- [ ] All tenant-specific requests include X-School-Slug header
- [ ] Test scripts extract IDs from responses for dependent requests
- [ ] Error responses are validated (401, 403, 404, 400, 500)
- [ ] Status codes use `.code` not `.status` (Postman API)
- [ ] Pre-request scripts initialize all required variables
- [ ] Folder structure groups requests logically
- [ ] No hardcoded tokens, IDs, or emails
- [ ] README explains how to import and run
- [ ] Environment file includes all required variables
- [ ] Collection works with Newman: `newman run collection.json -e environment.json`

## Output Format

Generate TWO files:

**1. school-portal-api-tests.postman_collection.json**
- Full Postman collection with all test requests
- Collection-level pre-request and test scripts
- Proper folder organization
- Dynamic ID and token extraction

**2. school-portal-local.postman_environment.json**
- Environment variables for local development
- All required base_url, credentials, and school_slug
- Template format for CI/CD environments

## Example Minimal Request

```json
{
  "name": "Login Admin",
  "request": {
    "method": "POST",
    "header": [
      { "key": "Content-Type", "value": "application/json" },
      { "key": "X-School-Slug", "value": "{{school_slug}}" }
    ],
    "body": {
      "mode": "raw",
      "raw": "{\"email\": \"{{admin_email}}\", \"password\": \"{{admin_pass}}\"}"
    },
    "url": {
      "raw": "{{base_url}}/api/auth/login/",
      "host": ["{{base_url}}"],
      "path": ["api", "auth", "login"]
    }
  },
  "event": [
    {
      "listen": "test",
      "script": {
        "type": "text/javascript",
        "exec": [
          "pm.test('Login successful', function () {",
          "  pm.expect(pm.response.code).to.equal(200);",
          "});",
          "",
          "if (pm.response.code === 200) {",
          "  const data = pm.response.json();",
          "  pm.collectionVariables.set('admin_token', data.access);",
          "  pm.collectionVariables.set('admin_refresh', data.refresh);",
          "}"
        ]
      }
    }
  ]
}
```

## Final Notes

- **Test in Collection Runner first** before using Newman
- **Postman's pre-request scripts execute BEFORE each request** - use for auth headers and variable setup
- **Test scripts execute AFTER each request** - use for validation and variable extraction
- **Use `pm.expect()` only in test scripts**, not pre-request scripts
- **Order matters** - ensure login runs before protected endpoints
- **Variables can be scoped:** global, environment (easier to override), collection (persists in this run)
- **Console.log won't work** - use `pm.test()` for debugging or inspect in Postman console
