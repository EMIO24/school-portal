# School Portal Postman Test Generation Guide

Use this alongside `POSTMAN_GENERATION_PROMPT.md` to generate accurate Postman tests for the School Portal API.

## Authentication Flow (Order Matters!)

Always execute requests in this sequence:

```
1. Health Check (GET /health/) - verify API is running
2. Login Admin (POST /api/auth/login/) - get admin JWT
3. [All protected admin endpoints] - use admin_token
4. Create Teacher (POST /api/staff/) - create test teacher
5. Login Teacher (POST /api/auth/login/) - get teacher JWT
6. [All protected teacher endpoints] - use teacher_token
7. Create Student (POST /api/students/) - create test student
8. Login Student (POST /api/auth/login/) - get student JWT
9. [All protected student endpoints] - use student_token
```

## Pre-request Script Requirements

Add to collection-level pre-request script:

```javascript
const cv = pm.collectionVariables;

// Initialize once per run
if (!cv.get('run_id')) {
  cv.set('run_id', String(Date.now()));
  cv.set('run_suffix', String(Date.now()).slice(-4));
  cv.set('today', new Date().toISOString().slice(0, 10));
}

const suffix = cv.get('run_suffix');

// Generate unique emails per run (avoid conflicts)
cv.set('teacher_email', `teacher.${suffix}@testschool.ng`);
cv.set('student_email', `student.${suffix}@testschool.ng`);

// Initialize token storage (empty until login)
['admin_token', 'teacher_token', 'student_token'].forEach(key => {
  if (!cv.get(key)) cv.set(key, '');
});

// Initialize ID storage (empty until created)
['session_id', 'term_id', 'level_id', 'arm_id', 'subject_id', 
 'teacher_id', 'staff_id', 'student_id', 'exam_id'].forEach(key => {
  if (!cv.get(key)) cv.set(key, '');
});
```

## Required Environment Variables

```json
{
  "name": "School Portal Local",
  "values": [
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
  ]
}
```

## Common Request Headers

**For ALL requests:**
```json
[
  { "key": "X-School-Slug", "value": "{{school_slug}}" }
]
```

**For authenticated requests (add to above):**
```json
{ "key": "Authorization", "value": "Bearer {{admin_token}}" }
```

**For JSON POST/PUT/PATCH:**
```json
{ "key": "Content-Type", "value": "application/json" }
```

## Endpoint Groups & Response Extraction

### 1. Health Check
```
GET {{base_url}}/health/

Expected: 200
No extraction needed
```

### 2. Authentication
```
POST {{base_url}}/api/auth/login/
Body: {"email": "{{admin_email}}", "password": "{{admin_pass}}"}

Response (200): {
  "access": "eyJhbGc...",
  "refresh": "eyJhbGc...",
  "role": "school_admin",
  "user": {"id": 1, "email": "...", ...}
}

Extract in test script:
pm.collectionVariables.set('admin_token', pm.response.json().access);
pm.collectionVariables.set('admin_id', pm.response.json().user.id);
```

### 3. Academic Sessions
```
POST {{base_url}}/api/sessions/
Body: {
  "name": "2024/2025",
  "starts_on": "2024-09-01",
  "ends_on": "2024-12-15"
}

Response (201): {"id": 1, "name": "2024/2025", ...}

Extract:
pm.collectionVariables.set('session_id', pm.response.json().id);
```

### 4. Academic Terms
```
POST {{base_url}}/api/terms/
Body: {
  "name": "First Term",
  "order": 1,
  "starts_on": "2024-09-01",
  "ends_on": "2024-11-30",
  "session": {{session_id}}
}

Response (201): {"id": 1, "name": "First Term", ...}

Extract:
pm.collectionVariables.set('term_id', pm.response.json().id);
```

### 5. Class Levels (Grade/Year)
```
POST {{base_url}}/api/class-levels/
Body: {"name": "JSS1", "order": 1}

Response (201): {"id": 1, "name": "JSS1", ...}

Extract:
pm.collectionVariables.set('level_id', pm.response.json().id);
```

### 6. Class Arms (Sections)
```
POST {{base_url}}/api/class-arms/
Body: {
  "name": "A",
  "level": {{level_id}},
  "total_students": 30
}

Response (201): {"id": 1, "name": "A", ...}

Extract:
pm.collectionVariables.set('arm_id', pm.response.json().id);
```

### 7. Subjects
```
POST {{base_url}}/api/subjects/
Body: {
  "name": "Mathematics",
  "code": "MTH"
}

Response (201): {"id": 1, "name": "Mathematics", ...}

Extract:
pm.collectionVariables.set('subject_id', pm.response.json().id);
```

### 8. Staff (Teachers)
```
POST {{base_url}}/api/staff/
Body: {
  "email": "{{teacher_email}}",
  "first_name": "John",
  "last_name": "Doe",
  "phone_number": "08012345678"
}

Response (201): {"id": 1, "email": "...", "user_id": 5, ...}

Extract BOTH:
pm.collectionVariables.set('staff_id', pm.response.json().id);
pm.collectionVariables.set('teacher_id', pm.response.json().user_id);
```

### 9. Students
```
POST {{base_url}}/api/students/
Body: {
  "email": "{{student_email}}",
  "first_name": "Jane",
  "last_name": "Smith",
  "admission_number": "ADM{{run_suffix}}"
}

Response (201): {"id": 1, "email": "...", "user_id": 6, ...}

Extract BOTH:
pm.collectionVariables.set('student_id', pm.response.json().id);
pm.collectionVariables.set('student_user_id', pm.response.json().user_id);
```

### 10. Subject Assignments
```
POST {{base_url}}/api/subject-assignments/
Body: {
  "staff": {{staff_id}},
  "subject": {{subject_id}},
  "class_arm": {{arm_id}}
}

Response (201): {"id": 1, ...}
```

### 11. Student Class Assignment
```
POST {{base_url}}/api/students/{{student_id}}/assign-class/
Body: {"class_arm": {{arm_id}}}

Response (200): {"id": 1, ...}
```

## Test Script Patterns

### For 201 (Created)
```javascript
pm.test("{{$ctrl.request.name}}", function () {
  pm.expect(pm.response.code).to.equal(201);
  const data = pm.response.json();
  
  // Extract ID if available
  if (data.id) {
    pm.collectionVariables.set('resource_id', String(data.id));
  }
  
  // Validate structure
  pm.expect(data).to.have.property('id');
  pm.expect(data).to.have.property('name');
});
```

### For 200 (Success)
```javascript
pm.test("{{$ctrl.request.name}}", function () {
  pm.expect(pm.response.code).to.equal(200);
});
```

### For List Endpoints (GET)
```javascript
pm.test("{{$ctrl.request.name}}", function () {
  pm.expect(pm.response.code).to.equal(200);
  const data = pm.response.json();
  
  // Handle both paginated and non-paginated
  const items = data.results || data;
  pm.expect(items).to.be.an('array');
  
  if (items.length > 0) {
    pm.collectionVariables.set('first_id', String(items[0].id));
  }
});
```

### For 204 (No Content)
```javascript
pm.test("{{$ctrl.request.name}}", function () {
  pm.expect(pm.response.code).to.equal(204);
});
```

### For Errors (401, 403, 404)
```javascript
pm.test("{{$ctrl.request.name}} - error handling", function () {
  // Expect either success OR specific error
  pm.expect([200, 201, 401, 404]).to.include(pm.response.code);
});
```

## Special Cases

### Pagination
```
GET {{base_url}}/api/sessions/?page=1&page_size=10

Response: {
  "count": 50,
  "next": "http://...",
  "previous": null,
  "results": [...]
}

Extract in test:
const count = pm.response.json().count;
pm.test(`Total items: ${count}`, function () {
  pm.expect(count).to.be.greaterThan(0);
});
```

### Bulk Operations
```
POST {{base_url}}/api/fees/schedule/
Body: [
  {"class_level": {{level_id}}, "amount": "25000.00", "due_date": "2024-09-30"},
  {"class_level": {{level_id2}}, "amount": "25000.00", "due_date": "2024-09-30"}
]

Response (207): {
  "created": 2,
  "errors": []
}

Test:
pm.expect([200, 201, 207]).to.include(pm.response.code);
```

### File Downloads
```
GET {{base_url}}/api/results/slip/{{student_id}}/

Expected headers:
Content-Type: application/pdf
Content-Disposition: attachment; filename="...pdf"

Test:
pm.test("PDF download", function () {
  pm.expect(pm.response.headers.get('Content-Type')).to.equal('application/pdf');
});
```

## Error Validation

Always include error handling for:

**400 Bad Request** - Missing or invalid fields
```javascript
if (pm.response.code === 400) {
  const errors = pm.response.json();
  pm.test("Validation errors present", function () {
    pm.expect(errors).to.have.any.keys(['field_name', 'email', 'password']);
  });
}
```

**401 Unauthorized** - Missing/expired token
```javascript
if (pm.response.code === 401) {
  pm.test("Auth error", function () {
    const error = pm.response.json();
    pm.expect(error).to.have.property('detail');
  });
}
```

**403 Forbidden** - Insufficient permissions
```javascript
if (pm.response.code === 403) {
  pm.test("Permission error", function () {
    const error = pm.response.json();
    pm.expect(['detail', 'error']).to.include(Object.keys(error)[0]);
  });
}
```

**404 Not Found** - Resource doesn't exist
```javascript
if (pm.response.code === 404) {
  pm.test("Not found", function () {
    pm.expect(pm.response.code).to.equal(404);
  });
}
```

## Cleanup (Final Requests)

Run after all tests to clean up:

```javascript
// DELETE /api/sessions/?id=in:1,2,3
// DELETE /api/class-levels/?id=in:1,2
// DELETE /api/staff/?id=in:1,2

// Or via test script:
sendRequest({
  method: 'DELETE',
  url: `{{base_url}}/api/sessions/{{session_id}}/`,
  header: authHeader(pm.collectionVariables.get('admin_token'))
}, (err, res) => {
  pm.test("Cleanup", function () { pm.expect([204, 404]).to.include(res.code); });
});
```

## Tips for Error-Free Generation

1. **Always use `{{variable_name}}`** - Never hardcode IDs, tokens, or emails
2. **Extract every ID** - Store created resource IDs for dependent requests
3. **Login before protected endpoints** - Token must exist before use
4. **Include Content-Type header** - For POST/PUT/PATCH with body
5. **Use `pm.response.code` not `.status`** - Postman API uses .code
6. **Test error cases** - Don't assume all requests succeed
7. **Use `to.include()` not `.equal()`** - For multiple acceptable statuses
8. **Check response structure** - Validate object has expected properties
9. **Handle pagination** - Use `.results` array if present
10. **Don't assume IDs** - Extract from response, never guess numbers

## Validation Checklist for Generated Collection

- [ ] All JSON is valid (use JSON validator)
- [ ] All variables use `{{name}}` format
- [ ] All protected requests have Authorization header
- [ ] All tenant requests have X-School-Slug header
- [ ] Content-Type: application/json on all POST/PUT/PATCH
- [ ] Every POST/PUT/PATCH response extracts IDs to variables
- [ ] Test scripts use `pm.test()` for assertions
- [ ] Test scripts use `pm.response.code` (not `.status`)
- [ ] Pre-request script initializes all variables
- [ ] Folder structure matches endpoint hierarchy
- [ ] No hardcoded tokens, IDs, or emails
- [ ] Can run in Postman Collection Runner
- [ ] Can run via Newman: `newman run collection.json -e environment.json`
- [ ] README explains import and execution steps
