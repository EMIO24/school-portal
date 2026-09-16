# Postman Test Generation - Complete Guide

## 📌 Overview

This directory contains **4 comprehensive guides** for generating error-free Postman tests for the School Portal API:

| File | Purpose |
|------|---------|
| `POSTMAN_GENERATION_PROMPT.md` | **Core principles** - Universal rules for ANY Postman collection |
| `POSTMAN_API_GENERATION_GUIDE.md` | **API-specific** - School Portal endpoints, request patterns, examples |
| `AI_POSTMAN_PROMPT_TEMPLATE.md` | **Ready-to-use** - Copy & paste prompt for Claude/ChatGPT |
| `POSTMAN_GENERATION_CHECKLIST.md` | **Validation** - Pre/post-generation checklist, troubleshooting |

---

## 🚀 Quick Start (Choose One Path)

### Path 1: AI Generation (Fastest - 5 min)
```
1. Open Claude or ChatGPT
2. Copy contents of: AI_POSTMAN_PROMPT_TEMPLATE.md
3. Paste into AI model and wait
4. Validate output: https://jsonlint.com
5. Import into Postman
6. Run collection
```

### Path 2: Manual Generation (Learning - 30 min)
```
1. Read: POSTMAN_GENERATION_PROMPT.md (principles)
2. Read: POSTMAN_API_GENERATION_GUIDE.md (specifics)
3. Create: school-portal-api-tests.postman_collection.json
4. Create: school-portal-local.postman_environment.json
5. Validate using POSTMAN_GENERATION_CHECKLIST.md
6. Import into Postman
```

### Path 3: Fix Existing (Debugging - 10 min)
```
1. Identify error using: POSTMAN_GENERATION_CHECKLIST.md
2. Find solution in: POSTMAN_GENERATION_PROMPT.md (section)
3. Apply fix to collection
4. Re-validate and test
```

---

## 📖 What Each File Contains

### 1. POSTMAN_GENERATION_PROMPT.md (Core Principles)
**Use this to understand HOW to generate error-free collections**

Contains:
- ✅ JSON schema compliance requirements
- ✅ JWT token management patterns
- ✅ Multi-tenant header requirements
- ✅ Request body formatting (JSON, files)
- ✅ Test script validation patterns
- ✅ Dynamic data generation
- ✅ Common error prevention
- ✅ Response handling patterns
- ✅ Validation checklist

When to use:
- Learning Postman collection structure
- Understanding best practices
- Fixing specific sections of a collection
- Reviewing someone else's collection

### 2. POSTMAN_API_GENERATION_GUIDE.md (School Portal Specifics)
**Use this to understand THE SCHOOL PORTAL API**

Contains:
- ✅ Authentication flow sequence (order matters!)
- ✅ Required pre-request script
- ✅ Environment variables needed
- ✅ 30+ actual endpoints with examples
- ✅ Request/response patterns for each
- ✅ Variable extraction rules
- ✅ Test script patterns for this API
- ✅ Special cases (pagination, bulk, files)
- ✅ Error validation
- ✅ Tips for error-free generation

When to use:
- Generating collection for this API
- Understanding endpoint structure
- Knowing what to extract from responses
- Understanding role-based access

### 3. AI_POSTMAN_PROMPT_TEMPLATE.md (Ready-to-Use)
**Copy this entire prompt into Claude/ChatGPT**

Contains:
- ✅ Complete API specifications
- ✅ All endpoint requirements
- ✅ Folder organization instructions
- ✅ Variable naming conventions
- ✅ Test coverage expectations
- ✅ Common mistakes to AVOID
- ✅ Response examples
- ✅ Output format specifications
- ✅ Validation checklist

When to use:
- Generating with AI model
- Want AI to create full collection
- Don't want to write collection manually
- Need quick generation

Result: AI generates 2 files:
- `school-portal-api-tests.postman_collection.json`
- `school-portal-local.postman_environment.json`

### 4. POSTMAN_GENERATION_CHECKLIST.md (Validation & Troubleshooting)
**Use this to validate and fix any issues**

Contains:
- ✅ Quick start guide (5 minutes)
- ✅ Pre-generation checklist
- ✅ Generation checklist (what to verify)
- ✅ Post-generation validation
- ✅ Common errors & fixes (15 scenarios)
- ✅ File reference table
- ✅ Success criteria
- ✅ Pro tips
- ✅ Troubleshooting flow chart
- ✅ Learning resources

When to use:
- Before generating (prep checklist)
- After generating (validation)
- Getting errors (troubleshooting)
- Need quick reference (tips)

---

## 🎯 Decision Tree

```
Do you want to:

Q1: Generate a NEW collection?
├─ YES: Q2
└─ NO: Q3

Q2: Using AI model (Claude/ChatGPT)?
├─ YES → Use: AI_POSTMAN_PROMPT_TEMPLATE.md
│        Then: POSTMAN_GENERATION_CHECKLIST.md (validation)
└─ NO  → Use: POSTMAN_GENERATION_PROMPT.md + POSTMAN_API_GENERATION_GUIDE.md
         Then: POSTMAN_GENERATION_CHECKLIST.md (validation)

Q3: Fix EXISTING collection?
├─ Getting errors?
│  └─ Use: POSTMAN_GENERATION_CHECKLIST.md (troubleshooting)
│     Then: POSTMAN_GENERATION_PROMPT.md (find pattern)
└─ Want to improve?
   └─ Use: POSTMAN_GENERATION_CHECKLIST.md (success criteria)
      Then: POSTMAN_API_GENERATION_GUIDE.md (specific endpoints)
```

---

## 🔑 Key Concepts (Quick Reference)

### 1. Variables (Never Hardcode)
```
❌ "Authorization": "Bearer eyJhbGc..."
✅ "Authorization": "Bearer {{admin_token}}"

❌ "url": "http://localhost:8000/api/sessions/123/"
✅ "url": "http://localhost:8000/api/sessions/{{session_id}}/"
```

### 2. Headers (Always Include)
```javascript
Every request:
- X-School-Slug: {{school_slug}}

JSON POST/PUT/PATCH:
- Content-Type: application/json

Protected endpoints:
- Authorization: Bearer {{token}}
```

### 3. Token Extraction
```javascript
// In test script (after login):
pm.collectionVariables.set('admin_token', pm.response.json().access);
```

### 4. ID Extraction
```javascript
// In test script (after create/POST):
if (pm.response.code === 201) {
  pm.collectionVariables.set('resource_id', String(pm.response.json().id));
}
```

### 5. Test Validation
```javascript
// Every test must have this:
pm.test('Test name', function () {
  pm.expect(pm.response.code).to.equal(200); // or 201, 204, etc
});
```

---

## ✅ Success Path

```
Step 1: PREPARE
├─ Read: POSTMAN_GENERATION_CHECKLIST.md (Quick Start section)
├─ Check: POSTMAN_GENERATION_CHECKLIST.md (Pre-generation Checklist)
└─ Know: API details, endpoints, auth method

Step 2: GENERATE
├─ Option A: Copy AI_POSTMAN_PROMPT_TEMPLATE.md → Paste in Claude → Get collection
├─ Option B: Follow POSTMAN_GENERATION_PROMPT.md + POSTMAN_API_GENERATION_GUIDE.md → Build manually
└─ Result: collection.json + environment.json

Step 3: VALIDATE
├─ Run: POSTMAN_GENERATION_CHECKLIST.md (Generation Checklist)
├─ Test: https://jsonlint.com (JSON validation)
├─ Import: Into Postman GUI
└─ Run: Collection Runner in Postman

Step 4: TEST
├─ Postman: Collection Runner → Should show ✓ passed
├─ CLI: newman run collection.json -e environment.json
└─ Result: Exit code 0 (success) = Ready!
```

---

## 🔴 Common Mistakes (Avoid These)

| Mistake | Fix | Reference |
|---------|-----|-----------|
| Hardcoded tokens | Use `{{admin_token}}` | POSTMAN_GENERATION_PROMPT.md #3 |
| Missing X-School-Slug | Add header to EVERY request | POSTMAN_API_GENERATION_GUIDE.md |
| Wrong Postman API | Use `pm.response.code` not `.status` | POSTMAN_GENERATION_PROMPT.md #6 |
| Test in pre-request | Use `pm.test()` only in test scripts | POSTMAN_GENERATION_PROMPT.md #6 |
| Invalid JSON | Check commas, quotes, brackets | POSTMAN_GENERATION_CHECKLIST.md |
| Login not first | Ensure login before protected endpoints | POSTMAN_API_GENERATION_GUIDE.md |
| No ID extraction | Extract after every POST | POSTMAN_API_GENERATION_GUIDE.md |
| Missing headers | Include Content-Type for JSON | POSTMAN_GENERATION_PROMPT.md #5 |

---

## 📊 File Dependencies

```
Your Choice
    ↓
├─ AI Mode: AI_POSTMAN_PROMPT_TEMPLATE.md ──→ Generate ──→ collection.json
│                                                              environment.json
│
└─ Manual Mode: POSTMAN_GENERATION_PROMPT.md
                + POSTMAN_API_GENERATION_GUIDE.md ──→ Create ──→ collection.json
                                                              environment.json
                    ↓
            POSTMAN_GENERATION_CHECKLIST.md ──→ Validate
                    ↓
              https://jsonlint.com ──→ Test JSON
                    ↓
                Postman GUI ──→ Import & Run Collection Runner
                    ↓
            Newman CLI ──→ Final verification
```

---

## 🎓 Learning Path

**Complete Beginner (45 min):**
1. Read: POSTMAN_GENERATION_PROMPT.md (20 min)
2. Read: POSTMAN_API_GENERATION_GUIDE.md (15 min)
3. Use: AI_POSTMAN_PROMPT_TEMPLATE.md (5 min)
4. Check: POSTMAN_GENERATION_CHECKLIST.md (5 min)

**Intermediate (20 min):**
1. Skim: POSTMAN_GENERATION_PROMPT.md (10 min)
2. Use: AI_POSTMAN_PROMPT_TEMPLATE.md (5 min)
3. Reference: POSTMAN_GENERATION_CHECKLIST.md (5 min)

**Advanced (5 min):**
1. Use: AI_POSTMAN_PROMPT_TEMPLATE.md (5 min)

---

## 💬 When to Use Each File

| Scenario | Use This File |
|----------|---------------|
| I want to understand Postman best practices | POSTMAN_GENERATION_PROMPT.md |
| I want to understand School Portal API | POSTMAN_API_GENERATION_GUIDE.md |
| I want to generate collection with AI | AI_POSTMAN_PROMPT_TEMPLATE.md |
| I need to validate/fix collection | POSTMAN_GENERATION_CHECKLIST.md |
| I got an error | POSTMAN_GENERATION_CHECKLIST.md → Common Errors |
| I want to learn step-by-step | POSTMAN_GENERATION_PROMPT.md + POSTMAN_API_GENERATION_GUIDE.md |
| I want quick reference | POSTMAN_GENERATION_CHECKLIST.md → Key Concepts |
| I need checklist | POSTMAN_GENERATION_CHECKLIST.md → All checklists |

---

## 📞 Troubleshooting Quick Links

Getting specific errors? Look here:

- **"Invalid JSON"** → POSTMAN_GENERATION_CHECKLIST.md → Common Errors → #1
- **"Variable not defined"** → POSTMAN_GENERATION_CHECKLIST.md → Common Errors → #2
- **"Bearer token invalid"** → POSTMAN_GENERATION_CHECKLIST.md → Common Errors → #3
- **"School not found"** → POSTMAN_GENERATION_CHECKLIST.md → Common Errors → #4
- **"Content-Type missing"** → POSTMAN_GENERATION_CHECKLIST.md → Common Errors → #5
- **"Response has no id"** → POSTMAN_GENERATION_CHECKLIST.md → Common Errors → #6
- **"Script runtime error"** → POSTMAN_GENERATION_CHECKLIST.md → Common Errors → #7

---

## 🎁 What You Get

After following this guide, you'll have:

✅ A **complete Postman collection** with:
- All 30+ endpoints
- Proper authentication handling
- Variable extraction
- Test validation
- Error handling

✅ An **environment file** with:
- Base URL
- Credentials
- School information
- Variable initialization

✅ The **ability to**:
- Run tests in Postman GUI
- Run tests via Newman CLI
- Integrate into CI/CD
- Debug API issues
- Document API behavior
- Regression test

✅ **Knowledge of**:
- Postman best practices
- JWT authentication in Postman
- Multi-tenant API testing
- Dynamic test data generation
- API validation patterns

---

## 🚀 Ready? Start Here

```
Choose ONE:

Option A (AI Generation - 5 min):
→ Open AI_POSTMAN_PROMPT_TEMPLATE.md
→ Copy entire content
→ Paste in Claude/ChatGPT
→ Wait for output
→ Validate in POSTMAN_GENERATION_CHECKLIST.md

Option B (Manual - 30 min):
→ Read POSTMAN_GENERATION_PROMPT.md
→ Read POSTMAN_API_GENERATION_GUIDE.md
→ Create collection.json + environment.json
→ Follow POSTMAN_GENERATION_CHECKLIST.md

Option C (Debug Existing - 10 min):
→ Open POSTMAN_GENERATION_CHECKLIST.md
→ Find your error
→ Apply fix
→ Re-validate
```

---

## 📝 Files in This Collection

```
/postman/
├── school-portal-api-tests.postman_collection.json (output)
├── school-portal-local.postman_environment.json (output)
├── README.md (how to use existing collection)
└── generate/ (this section)
    ├── POSTMAN_GENERATION_PROMPT.md (you are here)
    ├── POSTMAN_API_GENERATION_GUIDE.md
    ├── AI_POSTMAN_PROMPT_TEMPLATE.md
    ├── POSTMAN_GENERATION_CHECKLIST.md
    └── INDEX.md (this file)
```

---

## ✨ That's It!

You now have everything needed to generate error-free Postman collections for the School Portal API.

**Next Step:** Choose your path and get started! 🚀
