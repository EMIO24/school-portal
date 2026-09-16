# School Portal Testing Guide

Complete instructions for testing both the backend API and frontend application.

## Table of Contents

1. [Overview](#overview)
2. [Backend API Testing](#backend-api-testing)
3. [Frontend Testing](#frontend-testing)
4. [Test Coverage](#test-coverage)
5. [Troubleshooting](#troubleshooting)

---

## Overview

The school portal has three levels of testing:

| Type | Location | Technology | Scope |
|------|----------|-----------|-------|
| **E2E API Tests** | `tests/` folder | Bash + curl + jq | 19 integrated test suites |
| **Postman Collection** | `postman/` folder | Postman / Newman | Full API coverage with environment vars |
| **Frontend Tests** | `frontend/src/` | Jest + React Testing Library | UI component & integration tests |
| **Unit Tests** | `backend/*/tests.py` | Django TestCase | Individual model/view tests (placeholder) |

---

## Backend API Testing

### Prerequisites

Ensure your Docker environment is running:

```bash
docker compose up
```

Verify the API is healthy:

```bash
curl http://localhost:8000/health/
# Expected response: {"status":"ok"}
```

### Option 1: Full E2E Test Suite (Bash Scripts)

**File:** `run_tests.sh`  
**Coverage:** 19 test modules covering all major features  
**Duration:** ~2-5 minutes

#### Quick Start

```bash
# Run with defaults (localhost, testschool)
./run_tests.sh

# Run against staging/production
BASE_URL=https://your-railway-app.railway.app SCHOOL_SLUG=greenfield ./run_tests.sh

# Custom credentials
ADMIN_EMAIL=admin@myschool.ng ADMIN_PASS=MyPassword123 ./run_tests.sh
```

#### What Gets Tested

| Test Module | Tests | Purpose |
|-------------|-------|---------|
| `01_health.sh` | 1 | API health check endpoint |
| `02_auth.sh` | 5 | Admin login, token refresh, password change |
| `03_tenant.sh` | 3 | Multi-tenant school configuration |
| `04_cleanup.sh` | 1 | Pre-run cleanup of test data |
| `05_academics.sh` | 10 | Sessions, terms, holidays, calendar |
| `06_enrollment.sh` | 12 | Class levels, arms, subjects, teacher assignments |
| `07_attendance.sh` | 8 | Attendance tracking for students |
| `08_gradebook.sh` | 9 | Grade entry and retrieval |
| `09_results.sh` | 6 | Result publication workflows |
| `10_scratch_cards.sh` | 5 | Scratch card generation & validation |
| `11_cbt.sh` | 8 | Computer-based testing (exams, questions) |
| `12_fees.sh` | 7 | Fee categories, schedules, payments |
| `13_timetable.sh` | 6 | Period management, timetable entries |
| `14_notifications.sh` | 4 | SMS/Email notification templates |
| `15_analytics.sh` | 4 | Analytics computation & reporting |
| `16_promotion.sh` | 5 | Student promotion workflows |
| `17_parent.sh` | 4 | Parent student linking & dashboards |
| `18_security.sh` | 4 | Permission & role-based access tests |
| `19_cleanup.sh` | 1 | Post-run cleanup |

#### Example Output

```
[... building up test state ...]

══ AUTH — Admin login ══
  ✓ PASS POST /api/auth/login/ (admin) (HTTP 200)
  ✓ PASS POST /api/auth/login/ rejects bad credentials (HTTP 401)
  ✓ PASS POST /api/auth/token/refresh/ (HTTP 200)

══ ACADEMICS — Sessions ══
  ✓ PASS POST /api/sessions/ (HTTP 201)
  ✓ PASS GET /api/sessions/ (HTTP 200)

══════════════════════════════════
  PASS 127   FAIL 0   SKIP 0
══════════════════════════════════
```

#### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `FATAL: Admin login failed` | Wrong credentials or API unreachable | Check `BASE_URL` and `ADMIN_PASS` |
| `curl: command not found` | curl not installed | `apt install curl` |
| `jq: command not found` | jq not installed | `apt install jq` |
| `Connection refused` | API container not running | `docker compose up` |

---

### Option 2: Postman Collection

**Files:**
- `postman/school-portal-api-tests.postman_collection.json`
- `postman/school-portal-local.postman_environment.json`

#### Using Postman GUI

1. **Import Collection:**
   - Open Postman
   - File → Import → Select `school-portal-api-tests.postman_collection.json`

2. **Import Environment:**
   - File → Import → Select `school-portal-local.postman_environment.json`

3. **Configure Environment:**
   - Click the environment dropdown (top right)
   - Select "School Portal Local"
   - Set variables if needed:
     - `base_url`: `http://localhost:8000`
     - `school_slug`: `testschool`
     - `admin_email`: `admin@testschool.ng`
     - `admin_pass`: `AdminStr0ng#1`

4. **Run Collection:**
   - Click "Collection Runner" button
   - Select the imported collection
   - Click "Run"
   - Watch tests execute with automatic token management

#### Using Newman (CLI)

```bash
# Install Newman globally (if not already)
npm install -g newman

# Run collection against localhost
newman run postman/school-portal-api-tests.postman_collection.json \
  -e postman/school-portal-local.postman_environment.json

# Run against production with custom slug
newman run postman/school-portal-api-tests.postman_collection.json \
  -e postman/school-portal-local.postman_environment.json \
  --env-var "base_url=https://your-app.railway.app" \
  --env-var "school_slug=greenfield"

# Output as HTML report
newman run postman/school-portal-api-tests.postman_collection.json \
  -e postman/school-portal-local.postman_environment.json \
  -r html
```

#### What Postman Handles Automatically

- ✅ Stores admin, teacher, and student JWT tokens
- ✅ Generates unique test emails per run (prevents duplicates)
- ✅ Persists shared IDs (session_id, student_user_id, exam_id, etc.)
- ✅ Manages cookies automatically
- ✅ Accepts external integrations (Paystack, SMS services) with graceful status handling

---

### Option 3: Manual Django Unit Tests

**Location:** `backend/*/tests.py`

#### Run Django Tests

```bash
# Local development (without Docker)
cd backend
python manage.py test

# With Docker
docker compose exec web python manage.py test

# Run specific app
docker compose exec web python manage.py test accounts

# Run specific test class
docker compose exec web python manage.py test accounts.tests.YourTestClass

# Verbose output
docker compose exec web python manage.py test --verbosity=2
```

**Note:** Django test files currently contain placeholder code. Consider expanding with unit tests for models and views.

---

### Option 4: Single Endpoint Testing (curl)

**For quick ad-hoc testing:**

```bash
# Health check
curl -s http://localhost:8000/health/ | jq .

# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@testschool.ng","password":"AdminStr0ng#1"}' \
  | jq -r '.access')

# Use token to access protected endpoint
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "X-School-Slug: testschool" \
  http://localhost:8000/api/sessions/ | jq .
```

---

## Frontend Testing

### Prerequisites

Frontend is running at `http://localhost:3000`:

```bash
# If using Docker
docker compose up  # Frontend auto-starts

# Or locally without Docker
cd frontend
npm install
npm start
```

### Option 1: Jest Unit & Integration Tests

**Location:** `frontend/src/` (test files follow `*.test.js` pattern)

#### Run Tests

```bash
# Start test watcher (auto-rerun on file changes)
cd frontend
npm test

# Run once and exit
npm test -- --watchAll=false

# Run with coverage report
npm test -- --coverage --watchAll=false

# Run specific test file
npm test -- attendance.test.js
```

#### Creating New Tests

Example structure for testing a React component:

```javascript
// src/components/LoginForm.test.js
import { render, screen, fireEvent } from '@testing-library/react';
import LoginForm from './LoginForm';

describe('LoginForm Component', () => {
  test('renders login form', () => {
    render(<LoginForm />);
    expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
  });

  test('submits form with credentials', async () => {
    render(<LoginForm onSubmit={jest.fn()} />);
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /login/i }));
    // Assert submission happened
  });
});
```

### Option 2: Manual Browser Testing

1. **Navigate to frontend:** `http://localhost:3000`
2. **Test user flows:**
   - Login with admin credentials
   - Navigate between sections
   - Submit forms
   - Check error messages
   - Verify responsive design (resize browser)

### Option 3: Browser DevTools Testing

Use Chrome/Firefox DevTools to verify:

- **Network:** Check API requests, response times, error codes
- **Console:** Look for JavaScript errors or warnings
- **Performance:** Check component render times
- **Application:** Inspect stored tokens and user data

---

## Test Coverage

### Backend Coverage by Feature

| Feature | API Tests | Postman | Unit Tests | Status |
|---------|-----------|---------|-----------|--------|
| Authentication | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Academics (Sessions/Terms) | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Enrollment | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Attendance | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Gradebook | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Results | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| CBT (Computer-Based Testing) | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Fees & Payments | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Timetable | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Notifications | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Analytics | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Promotion | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Parent Portal | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |
| Security & Permissions | ✅ Yes | ✅ Yes | ⚠️ Partial | Ready |

### Frontend Coverage

| Component | Tests | Status |
|-----------|-------|--------|
| Login Page | ⚠️ Minimal | To expand |
| Dashboard | ⚠️ Minimal | To expand |
| Navigation | ⚠️ Minimal | To expand |
| Forms | ⚠️ Minimal | To expand |
| Tables | ⚠️ Minimal | To expand |

---

## Troubleshooting

### API Tests

**Problem:** Tests hang or timeout
```bash
# Solution: Check if API is responding
curl -v http://localhost:8000/health/

# Solution: Restart containers
docker compose restart web
```

**Problem:** "Connection refused" error
```bash
# Solution: Ensure containers are running
docker compose ps

# Solution: Start containers if stopped
docker compose up
```

**Problem:** Admin login fails
```bash
# Verify credentials in run_tests.sh
grep "ADMIN_EMAIL\|ADMIN_PASS" run_tests.sh

# Check if superuser exists
docker compose exec web python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> User.objects.filter(email='admin@testschool.ng').exists()
```

### Frontend Tests

**Problem:** Tests timeout
```bash
# Solution: Increase Jest timeout
npm test -- --testTimeout=10000
```

**Problem:** Module not found
```bash
# Solution: Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
npm test
```

### Postman Tests

**Problem:** "Invalid token" errors
```bash
# Solution: Check environment variables are set correctly
# Verify admin_pass matches your actual admin password
```

**Problem:** Requests timeout
```bash
# Solution: Increase Postman timeout
Settings → General → Request timeout (ms) → Set to 30000+
```

---

## Best Practices

### When Adding New Features

1. **Write API tests first** (`tests/XX_feature.sh`)
   - Define endpoint behavior
   - Test error cases
   - Test permissions

2. **Add Postman requests**
   - Mirror shell script tests
   - Use pre/post-request scripts for setup

3. **Add frontend tests**
   - Component render tests
   - User interaction tests
   - API integration tests

4. **Add Django unit tests**
   - Model validation tests
   - View permission tests
   - Serializer tests

### Test Data Management

- **Pre-run cleanup:** `04_cleanup.sh` removes old test data
- **Post-run cleanup:** `19_cleanup.sh` optionally cleans up after tests
- **Unique identifiers:** Tests generate unique emails using timestamps to avoid conflicts
- **Cascade deletes:** Sessions are deleted first (cascades to related data)

### CI/CD Integration

To integrate into CI/CD pipeline (GitHub Actions, GitLab CI):

```yaml
# Example: .github/workflows/test.yml
name: API Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
    steps:
      - uses: actions/checkout@v3
      - run: docker compose up -d
      - run: ./run_tests.sh
```

---

## Test Execution Quick Reference

```bash
# Full API test suite
./run_tests.sh

# API tests with custom URL
BASE_URL=https://staging.app ./run_tests.sh

# Postman CLI
newman run postman/school-portal-api-tests.postman_collection.json \
  -e postman/school-portal-local.postman_environment.json

# Frontend tests
cd frontend && npm test -- --watchAll=false

# Django unit tests
docker compose exec web python manage.py test

# Single endpoint test
curl -s http://localhost:8000/health/ | jq .
```

---

## Contact & Support

For test failures or issues:

1. Check the error message output
2. Review the relevant test file in `tests/` or `postman/`
3. Check the API logs: `docker compose logs web`
4. Verify Docker containers are running: `docker compose ps`

---

**Last Updated:** 2026-08-29
