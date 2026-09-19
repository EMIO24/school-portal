# Use This Prompt with Claude, ChatGPT, or Any AI Model

Copy and paste the text below into your AI model to generate a valid Postman collection for the School Portal API.

---

## PROMPT START

I need you to generate a **complete, error-free Postman Collection** for the School Portal API with the following specifications:

### API Details
- **Base URL:** http://localhost:8000
- **Authentication:** JWT (access/refresh tokens)
- **Multi-tenant:** Requires X-School-Slug header on all requests
- **School Slug:** testschool
- **Test Admin:** email=admin@testschool.ng, password=AdminStr0ng#1

### Collection Requirements

1. **Schema Compliance**
   - Must be valid Postman Collection v2.1.0
   - URL: https://schema.getpostman.com/json/collection/v2.1.0/collection.json
   - No syntax errors that would fail in Postman or Newman

2. **Authentication Handling**
   - Collection-level pre-request script that initializes variables
   - Login Admin endpoint (first request, stores admin_token)
   - Login Teacher endpoint (creates test teacher, stores teacher_token)
   - Login Student endpoint (creates test student, stores student_token)
   - All protected endpoints use Bearer token via `{{admin_token}}`, `{{teacher_token}}`, or `{{student_token}}`
   - No hardcoded tokens

3. **Multi-tenant Headers**
   - EVERY request includes: `X-School-Slug: {{school_slug}}`
   - No exceptions

4. **Dynamic Variable Generation**
   - Run ID (timestamp-based)
   - Run suffix (last 4 digits of timestamp)
   - Teacher email: `teacher.{{run_suffix}}@testschool.ng`
   - Student email: `student.{{run_suffix}}@testschool.ng`
   - Session name: `2024/2025-{{run_suffix}}`
   - All other names include run_suffix to avoid collisions

5. **Folder Organization**
   - Health Check
   - Authentication
   - Academic Management (Sessions, Terms, Holidays)
   - Enrollment (Levels, Arms, Subjects, Staff, Students)
   - Operations (Attendance, Gradebook, Results)
   - Advanced Features (CBT, Fees, Timetable, Analytics, Promotion)

6. **Endpoint Coverage** - Include these exact endpoints:

   **Health & Auth:**
   - GET /health/
   - POST /api/auth/login/ (admin)
   - POST /api/auth/token/refresh/
   - GET /api/auth/me/
   - POST /api/auth/change-password/

   **School Management:**
   - GET /api/school/me/
   - GET /api/schools/

   **Academics:**
   - POST /api/sessions/
   - GET /api/sessions/
   - GET /api/sessions/{{session_id}}/
   - POST /api/sessions/{{session_id}}/set-current/
   
   - POST /api/terms/
   - GET /api/terms/
   - POST /api/terms/{{term_id}}/set-current/
   
   - POST /api/holidays/
   - GET /api/holidays/
   - DELETE /api/holidays/{{holiday_id}}/

   **Enrollment - Structure:**
   - POST /api/class-levels/
   - GET /api/class-levels/
   
   - POST /api/class-arms/
   - GET /api/class-arms/
   
   - POST /api/subjects/
   - GET /api/subjects/
   
   - POST /api/staff/
   - GET /api/staff/
   - POST /api/subject-assignments/
   
   - POST /api/students/
   - GET /api/students/
   - POST /api/students/{{student_id}}/assign-class/

   **Operations:**
   - POST /api/attendance/sessions/
   - GET /api/attendance/sessions/
   - PATCH /api/attendance/sessions/{{att_session_id}}/submit/
   - GET /api/attendance/sessions/report/
   
   - GET /api/gradebook/entries/grade-scale/
   - POST /api/gradebook/entries/bulk-update/
   - POST /api/gradebook/entries/publish/
   
   - GET /api/results/class-results/
   - GET /api/results/slip/{{student_id}}/

   **Advanced:**
   - POST /api/cbt/topics/
   - GET /api/cbt/topics/
   - POST /api/cbt/questions/
   - GET /api/cbt/questions/
   - POST /api/cbt/exams/
   - GET /api/cbt/exams/
   
   - POST /api/fees/categories/
   - GET /api/fees/categories/
   - POST /api/fees/schedule/
   
   - POST /api/timetable/
   - GET /api/timetable/
   
   - POST /api/notifications/templates/
   - GET /api/notifications/

7. **Variable Extraction Pattern**
   - After each POST that returns 201: extract `id` field
   - After login endpoints: extract `access` and `refresh` tokens
   - After staff creation: extract both `id` and `user_id`
   - After student creation: extract both `id` and `user_id`
   - Store extracted values in collection variables for use in dependent requests
   - Example: If POST /api/sessions/ returns `{"id": 5, "name": "..."}`, store as `pm.collectionVariables.set('session_id', '5');`

8. **Test Script Validation**
   - Every request must have a test script that validates the response
   - Pattern 1 (for 201 Created): `pm.expect(pm.response.code).to.equal(201);`
   - Pattern 2 (for 200 OK): `pm.expect(pm.response.code).to.equal(200);`
   - Pattern 3 (for 204 No Content): `pm.expect(pm.response.code).to.equal(204);`
   - Pattern 4 (for multiple acceptable): `pm.expect([200, 404]).to.include(pm.response.code);`
   - Use `pm.test('Endpoint name', function() { ... });` wrapper
   - Use `pm.expect()` for assertions (NOT console.log)
   - Never use `pm.expect()` in pre-request scripts, only in test scripts

9. **Common Mistakes to AVOID**
   - ❌ Hardcoded tokens: `"Bearer eyJhbGci..."` → Instead use `"Bearer {{admin_token}}"`
   - ❌ Hardcoded IDs: `"session/12345/"` → Instead use `"session/{{session_id}}/"`
   - ❌ Hardcoded emails: `"teacher@test.com"` → Instead use `"{{teacher_email}}"`
   - ❌ Wrong Postman API: `pm.response.status` → Use `pm.response.code`
   - ❌ Wrong test location: Using assertions in pre-request script → Only use in test scripts
   - ❌ Missing Content-Type: POST/PUT without `application/json` header → Always include it
   - ❌ Status string comparison: `pm.expect(pm.response.status).to.equal("200 OK")` → Use `pm.response.code` with number
   - ❌ Missing X-School-Slug: Any request without it → Include on EVERY request
   - ❌ Variables not initialized: Undefined variables in requests → Initialize in pre-request script
   - ❌ Invalid JSON in body: Trailing commas or unescaped quotes → Validate JSON syntax

10. **Response Body Examples** (for reference)

    Login response:
    ```json
    {
      "access": "eyJhbGc...",
      "refresh": "eyJhbGc...",
      "role": "school_admin",
      "user": {"id": 1, "email": "admin@testschool.ng", ...}
    }
    ```

    Create Session response:
    ```json
    {
      "id": 1,
      "name": "2024/2025",
      "starts_on": "2024-09-01",
      "ends_on": "2024-12-15"
    }
    ```

    List endpoint response:
    ```json
    {
      "count": 5,
      "next": null,
      "previous": null,
      "results": [{"id": 1, "name": "..."}, ...]
    }
    ```

### Output Format

Generate TWO separate files:

**File 1: `school-portal-api-tests.postman_collection.json`**
- Complete Postman collection with proper v2.1.0 schema
- Valid JSON with no syntax errors
- Collection-level event handlers (pre-request and test scripts)
- All requests organized in folders
- Each request has URL, headers, body (if applicable), and test script
- Pre-request and test scripts are Postman JavaScript compatible

**File 2: `school-portal-local.postman_environment.json`**
- Environment file with:
  - `base_url`: http://localhost:8000
  - `school_slug`: testschool
  - `admin_email`: admin@testschool.ng
  - `admin_pass`: AdminStr0ng#1
  - Empty variables for: `admin_token`, `teacher_token`, `student_token`, and all ID variables
- Proper JSON structure

### Validation Checklist

Before submitting, verify:
- [ ] Valid JSON (no syntax errors)
- [ ] All variables in `{{variable_name}}` format
- [ ] All protected requests have `Authorization: Bearer {{token}}`
- [ ] ALL requests have `X-School-Slug: {{school_slug}}`
- [ ] All POST/PUT/PATCH have `Content-Type: application/json` header
- [ ] Post-login endpoints extract `access` token
- [ ] Post-create endpoints extract `id` field
- [ ] Every test uses `pm.response.code` (not .status)
- [ ] No hardcoded tokens, IDs, or emails
- [ ] Test scripts wrapped in `pm.test()` function
- [ ] Pre-request script initializes all variables
- [ ] Folders are logically organized
- [ ] Collection can run in Postman Collection Runner
- [ ] Collection can run via Newman CLI

### How It Will Be Used

The generated collection will be:
1. Imported into Postman GUI
2. Environment selected: "School Portal Local"
3. Run using Collection Runner
4. Also run via CLI: `newman run school-portal-api-tests.postman_collection.json -e school-portal-local.postman_environment.json`

Therefore, it MUST work in both contexts.

---

Generate the complete, error-free collection and environment files now.

## PROMPT END

---

## Usage Instructions

1. Copy everything between "PROMPT START" and "PROMPT END"
2. Paste into your AI model (Claude, ChatGPT, etc.)
3. The AI will generate the two JSON files
4. Validate the JSON output at: https://jsonlint.com/
5. Import into Postman and test
6. Use Newman CLI to validate: `newman run collection.json -e environment.json`

## If Generation Fails

Add clarifications to the prompt:

- **"Generate only the Postman collection, not explanations"** - for concise output
- **"Use the exact endpoint paths I provided"** - if paths are wrong
- **"Include full error handling tests"** - for comprehensive validation
- **"Add comments in JavaScript explaining each step"** - for debugging
- **"Format the collection with 2-space indentation"** - for readability

## Common Follow-up Requests

After initial generation, you can refine with:

- "Add a folder for CBT exam workflows with login flow"
- "Generate test data setup in pre-request script"
- "Add conditional tests for optional fields"
- "Generate bulk import test for CSV upload"
- "Add performance assertions (response time < 500ms)"
