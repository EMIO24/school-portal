# Quick Test Reference

## Prepared browser integration sandbox

See [the integration runbook](tests/integration/README.md) for local test accounts, CSV samples and workflow checks.

```powershell
python scripts/integration.py prepare
# Separate terminals:
python scripts/integration.py serve
npm --prefix frontend run start:integration
```

Open http://127.0.0.1:3001. Preparation results live in `.testing/readiness.json`; browser results are recorded separately in [RUN_RESULTS.md](tests/integration/RUN_RESULTS.md).

## 🚀 Start Testing Now

### Backend API - Option 1: Full Test Suite
```bash
./run_tests.sh
```
**Duration:** 2-5 min | **Tests:** 127 checks | **Coverage:** All major features

### Backend API - Option 2: Postman
```bash
# Create/update the local testschool tenant and test admin first.
bash setup_school.sh

# GUI: Import postman/ files into Postman app
# CLI: Install newman then run
newman run postman/school-portal-api-tests.postman_collection.json \
  -e postman/school-portal-local.postman_environment.json
```

### Frontend and backend contracts
```powershell
# From the repository root
npm --prefix frontend run audit:api
npm --prefix frontend run test:coverage
npm --prefix frontend run build

# From backend/ (temporary SQLite test database)
python manage.py test --settings=config.settings.test --noinput
```

The API audit checks frontend request paths and HTTP methods against Django without a running server. The frontend suite checks every page's router connection and includes workflow regression tests. See [FRONTEND_TEST_REPORT.md](FRONTEND_TEST_REPORT.md) for the current measured coverage and remaining gaps; passing tests do not imply 100% interaction coverage.

### Manual API Test
```bash
curl http://localhost:8000/health/
```

---

## 📋 Test Modules (run_tests.sh)

```
01_health           → API health
02_auth             → Login, tokens, passwords
03_tenant           → Multi-school config
04_cleanup          → Remove old test data
05_academics        → Sessions, terms, holidays
06_enrollment       → Classes, subjects, teacher assignments
07_attendance       → Attendance tracking
08_gradebook        → Grade entry
09_results          → Result publication
10_scratch_cards    → Scratch card tests
11_cbt              → Exams & questions
12_fees             → Fee management
13_timetable        → Timetable & periods
14_notifications    → SMS/Email templates
15_analytics        → Analytics computation
16_promotion        → Student promotion
17_parent           → Parent dashboards
18_security         → Permissions & roles
19_cleanup          → Post-test cleanup
```

---

## 🎯 Common Testing Scenarios

### Test Against Production
```bash
BASE_URL=https://your-app.railway.app SCHOOL_SLUG=greenfield ./run_tests.sh
```

### Test With Custom Admin Credentials
```bash
ADMIN_EMAIL=admin@myschool.ng ADMIN_PASS=MyPass123 ./run_tests.sh
```

### Test Specific Django App
```bash
docker compose exec web python manage.py test accounts
```

### Test Single Component (Frontend)
```bash
cd frontend
npm test LoginForm.test.js
```

### Check API Health
```bash
curl -s http://localhost:8000/health/ | jq .
```

### Get Admin Token (for manual testing)
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@testschool.ng","password":"AdminStr0ng#1"}' \
  | jq -r '.access')
echo $TOKEN
```

### Use Token to Test Endpoint
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  -H "X-School-Slug: testschool" \
  http://localhost:8000/api/sessions/ | jq .
```

---

## 🐛 Troubleshooting

| Issue | Command |
|-------|---------|
| API not responding | `docker compose ps` |
| Restart containers | `docker compose restart` |
| View API logs | `docker compose logs web` |
| Check migrations | `docker compose exec web python manage.py showmigrations` |
| Shell access | `docker compose exec web python manage.py shell` |
| Frontend build error | `cd frontend && npm install && npm test` |

---

## 📊 Test Coverage Summary

✅ = Covered | ⚠️ = Partial | ❌ = Not covered

| Feature | E2E API | Postman | Unit Tests |
|---------|---------|---------|-----------|
| Authentication | ✅ | ✅ | ⚠️ |
| Academics | ✅ | ✅ | ⚠️ |
| Enrollment | ✅ | ✅ | ⚠️ |
| Attendance | ✅ | ✅ | ⚠️ |
| Grades | ✅ | ✅ | ⚠️ |
| Results | ✅ | ✅ | ⚠️ |
| CBT | ✅ | ✅ | ⚠️ |
| Fees | ✅ | ✅ | ⚠️ |
| Timetable | ✅ | ✅ | ⚠️ |
| Notifications | ✅ | ✅ | ⚠️ |
| Analytics | ✅ | ✅ | ⚠️ |
| Security | ✅ | ✅ | ⚠️ |

---

## 📁 Test Files Location

```
school-portal/
├── run_tests.sh              # Main test runner
├── test_api.sh               # Alternative test script
├── tests/
│   ├── common.sh             # Shared helpers
│   ├── 01_health.sh          # Health checks
│   ├── 02_auth.sh            # Authentication
│   ├── ...                   # 19 test modules total
│   └── 19_cleanup.sh         # Cleanup
├── postman/
│   ├── school-portal-api-tests.postman_collection.json
│   ├── school-portal-local.postman_environment.json
│   └── README.md
├── frontend/
│   ├── src/
│   │   ├── __tests__/        # Jest test files
│   │   └── *.test.js         # Component tests
│   ├── package.json          # npm test
│   └── README.md
└── backend/
    ├── manage.py             # Django CLI
    ├── */tests.py            # Django unit tests
    └── TESTING_GUIDE.md      # Full guide (this file)
```

---

## ⏱️ Expected Durations

| Test Type | Duration | Notes |
|-----------|----------|-------|
| Health check | < 1 sec | Single endpoint |
| Full API suite | 2-5 min | 127 assertions |
| Postman collection | 3-7 min | Includes UI rendering |
| Frontend unit tests | 1-3 min | Depends on test count |
| Django unit tests | 1-2 min | Currently minimal |
| Manual testing | Variable | Ad-hoc |

---

## 🔗 Useful URLs (When Running Locally)

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- API Health: `http://localhost:8000/health/`
- API Docs (if enabled): `http://localhost:8000/api/docs/`

---

## 📝 Test Result Format

```
══ AUTH — Admin login ══
  ✓ PASS POST /api/auth/login/ (admin) (HTTP 200)
  ✓ PASS POST /api/auth/token/refresh/ (HTTP 200)
  ✗ FAIL POST /api/auth/logout/ — expected 200, got 401

══════════════════════════════════
  PASS 25   FAIL 1   SKIP 0
══════════════════════════════════
```

---

**For detailed guide, see:** [TESTING_GUIDE.md](./TESTING_GUIDE.md)


 opencode -s ses_f9712805effevbXq9cai10X6ug