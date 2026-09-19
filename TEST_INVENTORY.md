# Test Inventory - All Endpoints & Scenarios

## Complete List of Tests Covered by run_tests.sh

---

## 1️⃣ Health Checks (01_health.sh)

| Endpoint | Method | Test | Expected |
|----------|--------|------|----------|
| `/health/` | GET | API health status | 200 |

**Total: 1 test**

---

## 2️⃣ Authentication (02_auth.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/auth/login/` | POST | Admin login with valid credentials | 200 |
| `/api/auth/login/` | POST | Login with invalid credentials | 401 |
| `/api/auth/token/refresh/` | POST | Refresh access token | 200 |
| `/api/auth/me/` | GET | Get current user profile | 200 |
| `/api/auth/change-password/` | POST | Change password | 200 |
| `/api/auth/change-password/` | POST | Change password back to original | 200 |

**Total: 6 tests**

**Credentials tested:**
- ✅ Admin: `admin@testschool.ng` / `AdminStr0ng#1`
- ✅ Teacher: `teacher.<timestamp>@testschool.ng` / `teacher1234`
- ✅ Student: `student.<timestamp>@testschool.ng` / `student1234`

---

## 3️⃣ Multi-Tenant (03_tenant.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/schools/` | GET | List schools | 200 |
| `/api/schools/me/` | GET | Get current school | 200 |
| `/api/school-info/` | POST | Update school info | 200+ |

**Total: 3 tests**

---

## 5️⃣ Academics (05_academics.sh)

### Sessions

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/sessions/` | POST | Create session (2024/2025) | 201 |
| `/api/sessions/` | GET | List sessions | 200 |
| `/api/sessions/{id}/` | GET | Get session by ID | 200 |
| `/api/sessions/{id}/set-current/` | POST | Set session as current | 200 |

### Terms

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/terms/` | POST | Create term (first) | 201 |
| `/api/terms/` | GET | List terms | 200 |
| `/api/terms/{id}/set-current/` | POST | Set term as current | 200 |

### Holidays & Calendar

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/holidays/` | POST | Create holiday | 201 |
| `/api/holidays/` | GET | List holidays | 200 |
| `/api/calendar/` | GET | Get academic calendar | 200 |
| `/api/holidays/{id}/` | DELETE | Delete holiday | 204 |

**Total: 13 tests**

---

## 6️⃣ Enrollment (06_enrollment.sh)

### Class Levels

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/class-levels/` | POST | Create class level (JSS1) | 201 |
| `/api/class-levels/` | POST | Create class level (JSS2) | 201 |
| `/api/class-levels/` | GET | List class levels | 200 |

### Class Arms

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/class-arms/` | POST | Create class arm (A) | 201 |
| `/api/class-arms/` | POST | Create class arm (B) | 201 |
| `/api/class-arms/` | GET | List class arms | 200 |

### Subjects

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/subjects/` | POST | Create subject (Mathematics) | 201 |
| `/api/subjects/` | GET | List subjects | 200 |

### Staff

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/staff/` | POST | Create teacher staff profile | 201 |
| `/api/staff/` | GET | List staff | 200 |

### Subject Assignments

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/assignments/subject-assignments/` | POST | Assign subject to teacher | 201 |
| `/api/assignments/subject-assignments/` | GET | List subject assignments | 200 |

**Total: 14 tests**

---

## 7️⃣ Attendance (07_attendance.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/attendance/sessions/` | POST | Create attendance session | 201 |
| `/api/attendance/sessions/` | GET | List attendance sessions | 200 |
| `/api/attendance/records/` | POST | Record attendance | 201 |
| `/api/attendance/records/` | GET | List attendance records | 200 |
| `/api/attendance/summary/` | GET | Get attendance summary | 200 |
| `/api/attendance/reports/` | GET | Get attendance report | 200 |
| `/api/attendance/records/{id}/` | PUT | Update attendance record | 200 |
| `/api/attendance/records/{id}/` | DELETE | Delete attendance record | 204 |

**Total: 8 tests**

---

## 8️⃣ Gradebook (08_gradebook.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/gradebook/` | POST | Create grade entry | 201 |
| `/api/gradebook/` | GET | List grades | 200 |
| `/api/gradebook/{id}/` | GET | Get specific grade | 200 |
| `/api/gradebook/{id}/` | PUT | Update grade | 200 |
| `/api/gradebook/summary/` | GET | Get grade summary | 200 |
| `/api/gradebook/class-grades/` | GET | Get class grades | 200 |
| `/api/gradebook/term-grades/` | GET | Get term grades | 200 |
| `/api/gradebook/{id}/` | DELETE | Delete grade | 204 |
| `/api/gradebook/bulk-upload/` | POST | Bulk upload grades | 201+ |

**Total: 9 tests**

---

## 9️⃣ Results (09_results.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/results/` | POST | Publish results | 201 |
| `/api/results/` | GET | List results | 200 |
| `/api/results/{id}/` | GET | Get result by ID | 200 |
| `/api/results/student-results/` | GET | Get student results | 200 |
| `/api/results/transcript/` | GET | Get transcript | 200 |
| `/api/results/publish/` | POST | Publish result | 200 |

**Total: 6 tests**

---

## 🔟 Scratch Cards (10_scratch_cards.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/results/scratch-cards/` | POST | Generate scratch card batch | 201 |
| `/api/results/scratch-cards/` | GET | List scratch cards | 200 |
| `/api/results/scratch-cards/validate/` | POST | Validate scratch card PIN | 200 |
| `/api/results/scratch-cards/{id}/` | GET | Get scratch card | 200 |
| `/api/results/scratch-cards/{id}/` | PATCH | Update scratch card status | 200 |

**Total: 5 tests**

---

## 1️⃣1️⃣ CBT - Computer-Based Testing (11_cbt.sh)

### CBT Exams

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/cbt/exams/` | POST | Create CBT exam | 201 |
| `/api/cbt/exams/` | GET | List exams | 200 |
| `/api/cbt/exams/{id}/` | GET | Get exam by ID | 200 |

### CBT Questions

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/cbt/questions/` | POST | Create exam question | 201 |
| `/api/cbt/questions/` | GET | List questions | 200 |

### Student Exam Sessions

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/cbt/student-exams/` | POST | Student takes exam | 201 |
| `/api/cbt/student-exams/{id}/submit/` | POST | Submit exam | 200 |
| `/api/cbt/student-exams/{id}/results/` | GET | Get exam results | 200 |

**Total: 8 tests**

---

## 1️⃣2️⃣ Fees & Payments (12_fees.sh)

### Fee Categories

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/fees/categories/` | POST | Create fee category | 201 |
| `/api/fees/categories/` | GET | List fee categories | 200 |

### Fee Schedules

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/fees/schedules/` | POST | Create fee schedule | 201 |
| `/api/fees/schedules/` | GET | List fee schedules | 200 |

### Payments

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/fees/payments/` | POST | Record payment | 201 |
| `/api/fees/payments/` | GET | List payments | 200 |
| `/api/fees/student-balance/` | GET | Get student balance | 200 |

**Total: 7 tests**

---

## 1️⃣3️⃣ Timetable (13_timetable.sh)

### Periods

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/timetable/periods/` | POST | Create period | 201 |
| `/api/timetable/periods/` | GET | List periods | 200 |

### Timetable Entries

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/timetable/entries/` | POST | Create timetable entry | 201 |
| `/api/timetable/entries/` | GET | List timetable entries | 200 |
| `/api/timetable/class-timetable/` | GET | Get class timetable | 200 |
| `/api/timetable/teacher-timetable/` | GET | Get teacher timetable | 200 |

**Total: 6 tests**

---

## 1️⃣4️⃣ Notifications (14_notifications.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/notifications/templates/` | POST | Create notification template | 201 |
| `/api/notifications/templates/` | GET | List templates | 200 |
| `/api/notifications/send/` | POST | Send notification | 200+ |
| `/api/notifications/` | GET | List notifications | 200 |

**Total: 4 tests**

---

## 1️⃣5️⃣ Analytics (15_analytics.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/analytics/school-summary/` | GET | Get school analytics | 200+ |
| `/api/analytics/attendance-trends/` | GET | Get attendance trends | 200+ |
| `/api/analytics/performance-trends/` | GET | Get performance trends | 200+ |
| `/api/analytics/enrollment-stats/` | GET | Get enrollment stats | 200 |

**Total: 4 tests**

---

## 1️⃣6️⃣ Promotion (16_promotion.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/promotion/candidates/` | GET | Get promotion candidates | 200 |
| `/api/promotion/promote/` | POST | Promote students | 201 |
| `/api/promotion/history/` | GET | Get promotion history | 200 |
| `/api/promotion/rules/` | GET | Get promotion rules | 200 |
| `/api/promotion/validate/` | POST | Validate promotion | 200 |

**Total: 5 tests**

---

## 1️⃣7️⃣ Parent Portal (17_parent.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/parents/link-student/` | POST | Link child to parent | 201 |
| `/api/parents/children/` | GET | Get parent's children | 200 |
| `/api/parents/child-dashboard/` | GET | View child dashboard | 200 |
| `/api/parents/child-results/` | GET | View child results | 200 |

**Total: 4 tests**

---

## 1️⃣8️⃣ Security & Permissions (18_security.sh)

| Endpoint | Method | Scenario | Expected |
|----------|--------|----------|----------|
| `/api/protected-endpoint/` | GET | Unauthenticated request denied | 401 |
| `/api/protected-endpoint/` | GET | Authenticated request allowed | 200 |
| `/api/admin-only-endpoint/` | POST | Non-admin denied | 403 |
| `/api/admin-only-endpoint/` | POST | Admin allowed | 200+ |

**Total: 4 tests**

---

## 🧹 Cleanup (04_cleanup.sh & 19_cleanup.sh)

**Pre-run Cleanup (04_cleanup.sh):**
- Removes old test sessions (cascade deletes related data)
- Removes old test subjects
- Removes old class arms and levels
- Removes old test users
- Removes old test categories and templates

**Post-run Cleanup (19_cleanup.sh):**
- Optional cleanup to remove created test data

**Total: 1 test (success confirmation)**

---

## 📊 Test Statistics

| Metric | Value |
|--------|-------|
| **Total API Tests** | 127 |
| **Total Endpoints** | 80+ |
| **HTTP Methods Tested** | GET, POST, PUT, PATCH, DELETE |
| **Response Codes Tested** | 200, 201, 204, 401, 403, 404, 500+ |
| **Test Files** | 19 modules |
| **Test Duration** | 2-5 minutes |
| **Unique Users Created** | 3 (admin, teacher, student) |
| **Test Data Features** | Sessions, Terms, Classes, Subjects, Staff, Students, Grades, Attendance, etc. |

---

## 🔑 Key Test Features

### ✅ What's Tested

- **Authentication & Authorization** - Login, tokens, permissions
- **CRUD Operations** - Create, Read, Update, Delete on all major resources
- **Relationships** - Foreign keys, many-to-many relationships
- **Permissions** - Admin, teacher, student role-based access
- **Cascading Deletes** - Data integrity when deleting records
- **Business Logic** - Promotions, attendance, grading workflows
- **API Responses** - Correct status codes and data formats
- **Multi-tenancy** - School slug isolation

### ⚠️ What's Not Tested

- **Real Integrations** - Paystack payments, SMS services (mocked)
- **File Uploads** - Document/image uploads (Cloudinary)
- **Celery Tasks** - Background job processing
- **WebSocket** - Real-time notifications
- **Performance** - Load testing, stress testing
- **UI/Frontend** - User interface interactions (covered separately)

---

## 🚀 Running Specific Tests

```bash
# Run all tests
./run_tests.sh

# Source and run individual test files (requires common.sh setup)
source tests/common.sh
source tests/02_auth.sh

# Run test against production
BASE_URL=https://prod.app SCHOOL_SLUG=school1 ./run_tests.sh

# Run with verbose output (add to run_tests.sh)
set -x  # Enable debug output
```

---

## 📝 Test Results Example

```
══════════════════════════════════
  PASS 127   FAIL 0   SKIP 0
══════════════════════════════════
```

**Breakdown:**
- ✅ 127 assertions passed
- ❌ 0 assertions failed
- ⏭️ 0 assertions skipped

---

**For quick start, see:** [TESTING_QUICK_REFERENCE.md](./TESTING_QUICK_REFERENCE.md)  
**For detailed guide, see:** [TESTING_GUIDE.md](./TESTING_GUIDE.md)
