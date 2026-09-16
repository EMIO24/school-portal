# Postman Generation - Quick Start & Checklist

## 🚀 Quick Start (5 Minutes)

### Option 1: Use AI Model (Recommended)
1. Open Claude or ChatGPT
2. Copy contents of `AI_POSTMAN_PROMPT_TEMPLATE.md`
3. Paste into AI model
4. Wait for generation
5. Validate JSON at jsonlint.com
6. Import into Postman

### Option 2: Manual Generation
1. Read `POSTMAN_GENERATION_PROMPT.md` (core principles)
2. Reference `POSTMAN_API_GENERATION_GUIDE.md` (specific endpoints)
3. Create collection.json following the structure
4. Create environment.json with variables
5. Validate and test in Postman

---

## ✅ Pre-Generation Checklist

Before asking AI or creating manually:

- [ ] API base URL known: `http://localhost:8000`
- [ ] Authentication type: JWT (access/refresh tokens)
- [ ] Multi-tenant header: `X-School-Slug: testschool`
- [ ] Test credentials available: admin@testschool.ng / AdminStr0ng#1
- [ ] Know how many endpoints to include (~30-40 for full suite)
- [ ] Understand request sequence (login must come first)
- [ ] Know which responses return IDs (for variable extraction)

---

## ✅ Generation Checklist

While generating or reviewing collection:

### JSON Structure
- [ ] Valid JSON format (test at jsonlint.com)
- [ ] Has "info" object with name and schema
- [ ] Has "item" array with requests/folders
- [ ] Has "event" array with pre-request and test scripts
- [ ] Has "variable" array for collection variables

### Authentication
- [ ] Login endpoint is FIRST request in collection
- [ ] Login endpoint test script extracts `.access` token
- [ ] All protected endpoints have `Authorization: Bearer {{admin_token}}`
- [ ] No hardcoded tokens in any request
- [ ] Token variables initialized in pre-request script

### Headers
- [ ] ALL requests have: `X-School-Slug: {{school_slug}}`
- [ ] POST/PUT/PATCH have: `Content-Type: application/json`
- [ ] Protected requests have: `Authorization: Bearer {{token}}`
- [ ] No extra/invalid headers

### Variables
- [ ] All variables use `{{variable_name}}` format
- [ ] Variable names are descriptive (not `var1`, `v`, etc.)
- [ ] Variables initialized in collection pre-request script
- [ ] No hardcoded values in request bodies/URLs

### Request Bodies
- [ ] JSON is valid (proper escaping, no trailing commas)
- [ ] Uses variables for dynamic values: `{{teacher_email}}`
- [ ] Uses variables for IDs: `"session": {{session_id}}`
- [ ] Raw mode selected for JSON requests
- [ ] Proper nesting and field names

### Test Scripts
- [ ] Every request has a test script
- [ ] Test script wrapped in `pm.test('name', function() { ... })`
- [ ] Uses `pm.response.code` (NOT `.status`)
- [ ] Validates expected status codes
- [ ] Extracts IDs: `pm.collectionVariables.set('id', pm.response.json().id)`
- [ ] No console.log (use pm.test only)
- [ ] Error responses validated (401, 403, 404)

### Pre-request Script
- [ ] Initializes `run_id` and `run_suffix` once
- [ ] Generates unique emails: `teacher.{{run_suffix}}@school.ng`
- [ ] Initializes empty token variables
- [ ] Initializes empty ID variables
- [ ] Uses `pm.collectionVariables.set()` to store values

### Folder Organization
- [ ] Logical grouping (Health, Auth, Academic, Enrollment, etc.)
- [ ] Related endpoints grouped together
- [ ] Login/Auth endpoints come first
- [ ] Cleanup/deletion endpoints come last

---

## ✅ Post-Generation Validation

After generation:

### JSON Validation
- [ ] Paste into https://jsonlint.com - should show "Valid JSON"
- [ ] No syntax errors reported
- [ ] Can be parsed by JSON parser

### Postman Import Test
1. Open Postman
2. Click "Import"
3. Paste collection JSON
4. Should import without errors
5. Should import environment JSON
6. Select environment from dropdown

### Collection Runner Test
1. Click "Collection Runner"
2. Select "School Portal API Tests" collection
3. Select "School Portal Local" environment
4. Click "Run"
5. Should see test results (not errors)
6. Should see tokens extracted after login
7. Should see IDs extracted after creates

### Newman CLI Test
```bash
newman run school-portal-api-tests.postman_collection.json \
  -e school-portal-local.postman_environment.json
```

Should show:
- ✓ All requests executed
- ✓ Status codes match expected
- ✓ No JavaScript errors
- ✓ Exit code 0 (success)

---

## 🔴 Common Errors & Fixes

### Error: "Invalid JSON"
**Cause:** Syntax error in collection file
**Fix:** 
- Check for trailing commas: `{"name": "value",}` → remove comma
- Check for unescaped quotes: `"path": "value"name"` → escape inner quotes
- Use jsonlint.com to find exact line

### Error: "{{variable}} is not defined"
**Cause:** Variable not initialized before use
**Fix:**
- Add to pre-request script: `pm.collectionVariables.set('variable', 'value')`
- Or add to environment.json as initial value
- Check variable name matches exactly

### Error: "Bearer token invalid"
**Cause:** 
1. Login endpoint not run first
2. Token not extracted from login response
3. Token variable name wrong
**Fix:**
- Ensure login is first request
- Check login test script extracts `.access`
- Use exact token variable name: `{{admin_token}}`

### Error: "School not found / 404"
**Cause:** Missing `X-School-Slug` header
**Fix:**
- Add header to EVERY request: `X-School-Slug: {{school_slug}}`
- Check header name spelling: "X-School-Slug" (case-sensitive)
- Check value: `{{school_slug}}` not hardcoded

### Error: "Content-Type missing"
**Cause:** POST/PUT/PATCH missing Content-Type header
**Fix:**
- Add to every JSON request: `Content-Type: application/json`
- Should be in headers array, not body

### Error: "Response has no property 'id'"
**Cause:** Response structure different than expected
**Fix:**
- Check actual API response in browser/Postman
- May need to use different field: `.user_id` instead of `.id`
- Add null check: `if (data.id) { ... }`

### Error: "Script runtime error"
**Cause:** JavaScript syntax error in pre-request or test script
**Fix:**
- Check for semicolons at end of lines
- Check for matching brackets/parentheses
- Check for string quotes (must be matched)
- Test syntax in browser console first

---

## 📋 File Reference

| File | Purpose | Use When |
|------|---------|----------|
| `POSTMAN_GENERATION_PROMPT.md` | Universal Postman principles | Generating any API tests |
| `POSTMAN_API_GENERATION_GUIDE.md` | School Portal specific | Understanding this API |
| `AI_POSTMAN_PROMPT_TEMPLATE.md` | Ready-to-use prompt | Using with Claude/ChatGPT |
| `POSTMAN_GENERATION_CHECKLIST.md` | This file | Validating output |
| `postman/README.md` | How to run existing tests | Running the collection |
| `postman/school-portal-api-tests.postman_collection.json` | Actual collection | Import into Postman |
| `postman/school-portal-local.postman_environment.json` | Test environment | Configure credentials |

---

## 🎯 Success Criteria

Your Postman collection is ready when:

✅ **Structure**
- Valid JSON format
- Contains info, item, event, variable objects
- No syntax errors

✅ **Authentication**
- Login endpoint is first
- Tokens stored in variables
- All protected endpoints use Bearer token

✅ **Headers**
- Every request has X-School-Slug
- POST/PUT/PATCH have Content-Type: application/json
- Authorization header on protected requests

✅ **Variables**
- No hardcoded tokens, IDs, or emails
- All values use {{variable_name}} format
- Pre-request script initializes variables

✅ **Tests**
- Every request has test script
- Scripts validate response codes
- Scripts extract IDs from responses
- Scripts use pm.response.code (not .status)

✅ **Execution**
- Runs in Postman Collection Runner
- Runs via Newman CLI without errors
- Produces proper test report
- Exit code 0 (success)

---

## 💡 Pro Tips

1. **Always start with login** - Every test sequence must authenticate first
2. **Extract every ID** - You'll need them for dependent requests
3. **Use descriptive variables** - `session_id` is better than `id_1`
4. **Test error cases** - Validate 401, 403, 404 responses
5. **Don't trust defaults** - Explicitly set headers and status codes
6. **Run locally first** - Test in Postman GUI before Newman CLI
7. **Use Collection Runner** - Easier debugging than CLI
8. **Check timestamps** - Use `{{$timestamp}}` for unique values
9. **Log responses** - Add `console.log` in pre-request for debugging (Postman console)
10. **Keep it DRY** - Use collection-level scripts, not request-level repeats

---

## 📞 Troubleshooting Flow

```
Issue with generated collection?

1. Is JSON valid?
   └─ No → Fix syntax errors (commas, quotes, brackets)
   └─ Yes → Continue

2. Are variables defined?
   └─ No → Add to pre-request script
   └─ Yes → Continue

3. Are headers complete?
   └─ No → Add X-School-Slug and Authorization
   └─ Yes → Continue

4. Do test scripts validate?
   └─ No → Fix assertions (use pm.response.code)
   └─ Yes → Continue

5. Does it run in Postman?
   └─ No → Check Console tab for errors
   └─ Yes → Continue

6. Does it run in Newman?
   └─ No → Check output for specific error
   └─ Yes → ✅ Success!
```

---

## 📚 Learning Resources

- Postman Collection v2.1.0 Schema: https://schema.getpostman.com/json/collection/v2.1.0/collection.json
- Postman JavaScript API: https://learning.postman.com/docs/writing-scripts/script-references/postman-sandbox-api-reference/
- Postman Pre-request Scripts: https://learning.postman.com/docs/writing-scripts/pre-request-scripts/
- Postman Test Scripts: https://learning.postman.com/docs/writing-scripts/test-scripts/
- Newman CLI: https://learning.postman.com/docs/running-collections/using-newman-cli/

---

## 🎓 What You Just Created

You've created a Postman test suite that:
- ✅ Automatically authenticates with JWT tokens
- ✅ Handles multi-tenant isolation with headers
- ✅ Generates unique test data per run
- ✅ Extracts and reuses IDs across requests
- ✅ Validates all responses with proper status codes
- ✅ Can run in GUI or CLI
- ✅ Produces professional test reports
- ✅ Prevents common API testing errors

Perfect for:
- 🔄 CI/CD pipelines
- 📊 Regression testing
- 🐛 Bug reproduction
- 🔍 API documentation
- ✅ Quality assurance
