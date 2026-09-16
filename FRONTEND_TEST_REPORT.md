# Frontend test report

Generated: 2026-09-07T17:48:10.726Z

- Tests: **234 passed, 0 failed, 0 skipped** across 18 suites.
- Coverage: **60.9% lines**, 58.37% statements, 52.23% branches, 45.65% functions.
- API audit: **179 request variants at 176 call sites; 0 unresolved paths or unsupported methods**.
- Page routing: **43 pages; all have concrete route elements (regression test passed)**.
- Production build: **passed without compiler/lint warnings**.
- Backend tests: **14 tests passed against isolated test settings**.

## Verified fixes

- Staff CSV uses staff-only required columns, the staff upload endpoint, and staff labels. CSV preview handles quoted commas, escaped quotes, multiline fields, BOM, empty input, invalid columns, and incomplete rows.
- Frontend API paths use Django routes, including exam results. The audit includes services, fetch/axios calls, variable URLs, both domain-rating endpoints, and both import configurations.
- Role navigation exposes the registered pages, including linked-child result and fee pages. Tests render each declared page route, check navigation destinations, and verify nested unknown-route fallbacks and the superadmin landing route.
- Student profile/class IDs survive authentication normalization. Fees and performance use profile IDs; results, attendance, and gradebook use account IDs; timetables use class IDs. Enrollment and staff lists expose both identifiers.
- Timetable teachers use account IDs from staff-list responses. Staff editing uses the profile PATCH contract and nullable date fields.
- PDF, ZIP, CSV, and receipt downloads use the authenticated API client. API origin and tenant headers are shared across authenticated requests, parent login, school branding, and public result checking.
- Workflow tests cover timetable creation, staff editing, exam-result loading and gradebook push, template CRUD, fee schedules, attendance saving/locking, and gradebook draft/publish.
- CI checks frontend tests, API contracts and the production build before deployment.

## Coverage limits

**This is not 100% interaction coverage or a flawless-system certification.** The line coverage denominator includes every page, shared component, and App.js; files and unexecuted branches are not excluded to inflate the number. Service/context tests also run, but are outside this comparable coverage denominator.

Frontend tests use jsdom and mocked HTTP responses. Route tests isolate page components to verify router wiring. The Django audit verifies registered paths and methods, not every request payload, permission decision, response schema, or live service outcome. Dynamic resource IDs use a representative value of 1; configured backend origins are stripped for resolution. External Cloudinary uploads and service-worker asset fetches are outside the backend route audit.

The isolated backend suite additionally verifies student/staff profile serialization, real staff CSV import against a temporary SQLite database, duplicate rows, rejected roles/tenants, and payment-provider failures. PostgreSQL-specific behavior, full live browser journeys, and external notifications/payments still require integration testing.

## Coverage by file

| File | Lines | Branches |
|---|---:|---:|
| [src/App.js](frontend/src/App.js) | 100% | 87.5% |
| [src/components/admin/BulkImport.jsx](frontend/src/components/admin/BulkImport.jsx) | 85.85% | 85.14% |
| [src/components/cbt/QuestionEditor.jsx](frontend/src/components/cbt/QuestionEditor.jsx) | 67.16% | 74.11% |
| [src/components/common/LoadingScreen.jsx](frontend/src/components/common/LoadingScreen.jsx) | 100% | 100% |
| [src/components/common/PortalNavigation.jsx](frontend/src/components/common/PortalNavigation.jsx) | 100% | 83.33% |
| [src/components/common/ProtectedRoute.jsx](frontend/src/components/common/ProtectedRoute.jsx) | 100% | 92.3% |
| [src/components/common/ThemeProvider.jsx](frontend/src/components/common/ThemeProvider.jsx) | 100% | 90% |
| [src/components/teacher/GradeCell.jsx](frontend/src/components/teacher/GradeCell.jsx) | 96.77% | 92.85% |
| [src/components/timetable/EntryModal.jsx](frontend/src/components/timetable/EntryModal.jsx) | 90.47% | 75.92% |
| [src/components/timetable/TimetableGrid.jsx](frontend/src/components/timetable/TimetableGrid.jsx) | 85.36% | 88.7% |
| [src/pages/admin/AdminDashboard.jsx](frontend/src/pages/admin/AdminDashboard.jsx) | 68.57% | 73.17% |
| [src/pages/admin/AttendanceOverview.jsx](frontend/src/pages/admin/AttendanceOverview.jsx) | 35.48% | 20% |
| [src/pages/admin/BulkImportPage.jsx](frontend/src/pages/admin/BulkImportPage.jsx) | 87.5% | 71.42% |
| [src/pages/admin/CalendarSettings.jsx](frontend/src/pages/admin/CalendarSettings.jsx) | 20.88% | 12.78% |
| [src/pages/admin/ExamManager.jsx](frontend/src/pages/admin/ExamManager.jsx) | 40.16% | 28.03% |
| [src/pages/admin/ExamResults.jsx](frontend/src/pages/admin/ExamResults.jsx) | 90.16% | 70% |
| [src/pages/admin/FeeCollection.jsx](frontend/src/pages/admin/FeeCollection.jsx) | 32.05% | 19.14% |
| [src/pages/admin/FeeSetup.jsx](frontend/src/pages/admin/FeeSetup.jsx) | 72% | 59.61% |
| [src/pages/admin/NotificationTemplates.jsx](frontend/src/pages/admin/NotificationTemplates.jsx) | 85% | 71.42% |
| [src/pages/admin/Notifications.jsx](frontend/src/pages/admin/Notifications.jsx) | 80.43% | 48.21% |
| [src/pages/admin/Promotion.jsx](frontend/src/pages/admin/Promotion.jsx) | 34.54% | 25% |
| [src/pages/admin/QuestionBank.jsx](frontend/src/pages/admin/QuestionBank.jsx) | 54.54% | 44.64% |
| [src/pages/admin/ResultManagement.jsx](frontend/src/pages/admin/ResultManagement.jsx) | 32.94% | 20.48% |
| [src/pages/admin/ScratchCards.jsx](frontend/src/pages/admin/ScratchCards.jsx) | 34.84% | 23.52% |
| [src/pages/admin/Staff.jsx](frontend/src/pages/admin/Staff.jsx) | 50% | 17.5% |
| [src/pages/admin/StaffForm.jsx](frontend/src/pages/admin/StaffForm.jsx) | 57.77% | 67.61% |
| [src/pages/admin/StaffProfilePage.jsx](frontend/src/pages/admin/StaffProfilePage.jsx) | 86.36% | 66.66% |
| [src/pages/admin/StudentForm.jsx](frontend/src/pages/admin/StudentForm.jsx) | 100% | 100% |
| [src/pages/admin/StudentProfile.jsx](frontend/src/pages/admin/StudentProfile.jsx) | 46.05% | 55.22% |
| [src/pages/admin/Students.jsx](frontend/src/pages/admin/Students.jsx) | 100% | 100% |
| [src/pages/admin/SubjectAssignment.jsx](frontend/src/pages/admin/SubjectAssignment.jsx) | 31.4% | 21.73% |
| [src/pages/admin/SubjectManager.jsx](frontend/src/pages/admin/SubjectManager.jsx) | 34.4% | 40% |
| [src/pages/admin/TimetableBuilder.jsx](frontend/src/pages/admin/TimetableBuilder.jsx) | 83.01% | 88.46% |
| [src/pages/parent/ChildDetails.jsx](frontend/src/pages/parent/ChildDetails.jsx) | 93.75% | 75% |
| [src/pages/parent/ParentDashboard.jsx](frontend/src/pages/parent/ParentDashboard.jsx) | 67.56% | 57.14% |
| [src/pages/parent/ParentLogin.jsx](frontend/src/pages/parent/ParentLogin.jsx) | 81.13% | 70.58% |
| [src/pages/public/ChangePassword.jsx](frontend/src/pages/public/ChangePassword.jsx) | 84.74% | 62.29% |
| [src/pages/public/CheckResult.jsx](frontend/src/pages/public/CheckResult.jsx) | 61.9% | 32.65% |
| [src/pages/public/Login.jsx](frontend/src/pages/public/Login.jsx) | 93.02% | 84.61% |
| [src/pages/student/ExamList.jsx](frontend/src/pages/student/ExamList.jsx) | 59.09% | 13.79% |
| [src/pages/student/ExamReview.jsx](frontend/src/pages/student/ExamReview.jsx) | 75% | 46.66% |
| [src/pages/student/ExamRoom.jsx](frontend/src/pages/student/ExamRoom.jsx) | 72.81% | 56.41% |
| [src/pages/student/Fees.jsx](frontend/src/pages/student/Fees.jsx) | 86.04% | 71.73% |
| [src/pages/student/MyAttendance.jsx](frontend/src/pages/student/MyAttendance.jsx) | 96.29% | 76.19% |
| [src/pages/student/MyPerformance.jsx](frontend/src/pages/student/MyPerformance.jsx) | 53.12% | 23.4% |
| [src/pages/student/MyResult.jsx](frontend/src/pages/student/MyResult.jsx) | 65.9% | 36.73% |
| [src/pages/student/StudentDashboard.jsx](frontend/src/pages/student/StudentDashboard.jsx) | 100% | 100% |
| [src/pages/student/Timetable.jsx](frontend/src/pages/student/Timetable.jsx) | 96.29% | 100% |
| [src/pages/teacher/AffinityDomain.jsx](frontend/src/pages/teacher/AffinityDomain.jsx) | 37.2% | 33.33% |
| [src/pages/teacher/MyTimetable.jsx](frontend/src/pages/teacher/MyTimetable.jsx) | 69.23% | 40% |
| [src/pages/teacher/ScoreEntry.jsx](frontend/src/pages/teacher/ScoreEntry.jsx) | 81.81% | 73.63% |
| [src/pages/teacher/TakeAttendance.jsx](frontend/src/pages/teacher/TakeAttendance.jsx) | 73.45% | 70.11% |
| [src/pages/teacher/TeacherDashboard.jsx](frontend/src/pages/teacher/TeacherDashboard.jsx) | 100% | 100% |

## API contract failures

None in the extracted frontend request variants.

## Rerun

From the repository root:

```powershell
npm --prefix frontend run audit:api
npm --prefix frontend run test:coverage
npm --prefix frontend run build > frontend/build-test-results.txt 2>&1
node frontend/scripts/report-frontend-tests.cjs
```

The API audit needs the backend Python dependencies installed, but no running server or database. For the isolated backend tests, run from `backend/`:

```powershell
python manage.py test --settings=config.settings.test --noinput
```

Artifacts: [test results](frontend/test-results.json), [HTML coverage](frontend/coverage/lcov-report/index.html), [API route audit](frontend/api-route-results.json).
