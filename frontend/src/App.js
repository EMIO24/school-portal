import UserGuide from "./pages/public/UserGuide";
import PortalDesigns from "./pages/platform/PortalDesigns";
import { PaymentReturn, Subscription, PlatformPayments } from './pages/payments/Payments';
/**
 * src/App.jsx
 *
 * Root application component — full route tree for all roles.
 *
 * Provider order: BrowserRouter → ThemeProvider → AuthProvider
 */

import React from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

// ── Providers ──────────────────────────────────────────────────────────────
import ThemeProvider from "./components/common/ThemeProvider";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/common/ProtectedRoute";

// ── Public ─────────────────────────────────────────────────────────────────
import PlatformTeam from "./pages/platform/PlatformTeam";
import PlatformDashboard from "./pages/platform/PlatformDashboard";
import SchoolSignup from "./pages/platform/SchoolSignup";
import Login          from "./pages/public/Login";
import ChangePassword from "./pages/public/ChangePassword";
import CheckResult    from "./pages/public/CheckResult";

// ── Admin pages ────────────────────────────────────────────────────────────
import AdminDashboard   from "./pages/admin/AdminDashboard";
import AcademicSetupWizard from "./pages/admin/AcademicSetupWizard";
import CalendarSettings from "./pages/admin/CalendarSettings";
import Students         from "./pages/admin/Students";
import StudentForm      from "./pages/admin/StudentForm";
import StudentProfilePage from "./pages/admin/StudentProfile";
import Staff            from "./pages/admin/Staff";
import StaffForm        from "./pages/admin/StaffForm";
import StaffProfilePage from "./pages/admin/StaffProfilePage";
import BulkImportPage   from "./pages/admin/BulkImportPage";
import ResultManagement from "./pages/admin/ResultManagement";
import ScratchCards     from "./pages/admin/ScratchCards";
import QuestionBank     from "./pages/admin/QuestionBank";
import ExamManager     from "./pages/admin/ExamManager";
import ExamResults     from "./pages/admin/ExamResults";

// ── Role dashboards (stubs) ────────────────────────────────────────────────
import TeacherDashboard from "./pages/teacher/TeacherDashboard";
import StudentDashboard from "./pages/student/StudentDashboard";
import ParentDashboard  from "./pages/parent/ParentDashboard";
import ParentLogin      from "./pages/parent/ParentLogin";
import ChildDetails from "./pages/parent/ChildDetails";
import MyResult         from "./pages/student/MyResult";
import ExamList         from "./pages/student/ExamList";
import ExamRoom         from "./pages/student/ExamRoom";
import ExamReview       from "./pages/student/ExamReview";
import StudentFees      from "./pages/student/Fees";

// ── Phase 4 admin pages ────────────────────────────────────────────────────
import Notifications          from "./pages/admin/Notifications";
import NotificationTemplates  from "./pages/admin/NotificationTemplates";
import FeeSetup               from "./pages/admin/FeeSetup";
import FeeCollection          from "./pages/admin/FeeCollection";

// ── Phase 5 pages ──────────────────────────────────────────────────────────
import Promotion        from "./pages/admin/Promotion";
import MyPerformance    from "./pages/student/MyPerformance";

// ── Helpers ────────────────────────────────────────────────────────────────
import { useAuth } from "./hooks/useAuth";
import { ROLE_DASHBOARDS } from "./utils/roles";
import LoadingScreen from "./components/common/LoadingScreen";
import PortalNavigation from "./components/common/PortalNavigation";
import AttendanceOverview from './pages/admin/AttendanceOverview';
import SubjectAssignment from './pages/admin/SubjectAssignment';
import SubjectManager from './pages/admin/SubjectManager';
import TimetableBuilder from './pages/admin/TimetableBuilder';
import MyAttendance from './pages/student/MyAttendance';
import StudentTimetable from './pages/student/Timetable';
import AffinityDomain from './pages/teacher/AffinityDomain';
import MyTimetable from './pages/teacher/MyTimetable';
import ScoreEntry from './pages/teacher/ScoreEntry';
import TakeAttendance from './pages/teacher/TakeAttendance';

function RootRedirect() {
  const { isAuthenticated, isLoading, user } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <Navigate to={ROLE_DASHBOARDS[user.role] || "/login"} replace />;
}

function AppRoutes() {
  return (
    <Routes>

      {/* ── Public ───────────────────────────────────────────────────────── */}
      <Route path="/register-school" element={<SchoolSignup />} />
      <Route path="/platform/change-password" element={<ProtectedRoute allowedRoles={["superadmin"]}><ChangePassword /></ProtectedRoute>} />
      <Route path="/platform/login" element={<Login platform />} />
      <Route path="/login"           element={<Login />} />
      <Route path="/parent/login"    element={<ParentLogin />} />
      <Route path="/check-result"    element={<CheckResult />} />
      <Route path="/change-password" element={
        <ProtectedRoute><ChangePassword /></ProtectedRoute>
      } />

      {/* ── School Admin ─────────────────────────────────────────────────── */}
      <Route path="/admin/*" element={
        <ProtectedRoute allowedRoles={["school_admin"]}>
          <Routes>
            <Route path="setup-wizard"        element={<AcademicSetupWizard />} />
            <Route path="dashboard"            element={<AdminDashboard />} />
            <Route path="attendance" element={<AttendanceOverview />} />
            <Route path="subjects" element={<SubjectManager />} />
            <Route path="subject-assignments" element={<SubjectAssignment />} />
            <Route path="timetable" element={<TimetableBuilder />} />

            {/* Calendar */}
            <Route path="calendar"             element={<CalendarSettings />} />

            {/* Students */}
            <Route path="students"             element={<Students />} />
            <Route path="students/new"         element={<StudentForm />} />
            <Route path="students/import"      element={
              <BulkImportPage type="students" />
            } />
            <Route path="students/:id"         element={<StudentProfilePage />} />
            <Route path="students/:id/edit"    element={<StudentForm />} />

            {/* Staff */}
            <Route path="staff"                element={<Staff />} />
            <Route path="staff/new"            element={<StaffForm />} />
            <Route path="staff/import"         element={
              <BulkImportPage type="staff" />
            } />
            <Route path="staff/:id"            element={<StaffProfilePage />} />
            <Route path="staff/:id/edit"       element={<StaffForm />} />

            {/* Results & Scratch Cards */}
            <Route path="results"       element={<ResultManagement />} />
            <Route path="scratch-cards" element={<ScratchCards />} />

            {/* CBT */}
            <Route path="question-bank"  element={<QuestionBank />} />
            <Route path="exam-manager"   element={<ExamManager />} />
            <Route path="exam-results"   element={<ExamResults />} />

            {/* Notifications */}
            <Route path="notifications"           element={<Notifications />} />
            <Route path="notification-templates"  element={<NotificationTemplates />} />

            {/* Fees */}
            <Route path="subscription" element={<Subscription />} />
            <Route path="fee-setup"      element={<FeeSetup />} />
            <Route path="fee-collection" element={<FeeCollection />} />

            {/* Promotion */}
            <Route path="promotion" element={<Promotion />} />
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
          </Routes>
        </ProtectedRoute>
      } />

      {/* ── Teacher ──────────────────────────────────────────────────────── */}
      <Route path="/teacher/*" element={
        <ProtectedRoute allowedRoles={["teacher"]}>
          <Routes>
            <Route path="dashboard" element={<TeacherDashboard />} />
            <Route path="attendance" element={<TakeAttendance />} />
            <Route path="scores" element={<ScoreEntry />} />
            <Route path="domains" element={<AffinityDomain />} />
            <Route path="timetable" element={<MyTimetable />} />
            {/*
              Upcoming teacher routes:
              <Route path="classes"      element={<MyClasses />} />
              <Route path="attendance"   element={<Attendance />} />
              <Route path="scores"       element={<ScoreEntry />} />
              <Route path="cbt"          element={<CBTManage />} />
            */}
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
          </Routes>
        </ProtectedRoute>
      } />

      {/* ── Student ──────────────────────────────────────────────────────── */}
      <Route path="/student/*" element={
        <ProtectedRoute allowedRoles={["student"]}>
          <Routes>
            <Route path="dashboard" element={<StudentDashboard />} />
            <Route path="attendance" element={<MyAttendance />} />
            <Route path="timetable" element={<StudentTimetable />} />
            {/* Results */}
            <Route path="results" element={<MyResult />} />

            {/* CBT */}
            <Route path="exams"               element={<ExamList />} />
            <Route path="exam/:examId"        element={<ExamRoom />} />
            <Route path="exam/:examId/review" element={<ExamReview />} />

            {/* Fees */}
            <Route path="fees" element={<StudentFees />} />

            {/* Performance */}
            <Route path="performance" element={<MyPerformance />} />
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
          </Routes>
        </ProtectedRoute>
      } />

      {/* ── Parent ───────────────────────────────────────────────────────── */}
      <Route path="/parent/*" element={
        <ProtectedRoute allowedRoles={["parent"]}>
          <Routes>
            <Route path="dashboard" element={<ParentDashboard />} />
            <Route path="results/:studentId" element={<ChildDetails mode="results" />} />
            <Route path="fees/:studentId" element={<ChildDetails mode="fees" />} />
            {/*
              Upcoming parent routes:
              <Route path="children"   element={<MyChildren />} />
              <Route path="results"    element={<ChildResults />} />
              <Route path="fees"       element={<FeeStatus />} />
            */}
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="*" element={<Navigate to="dashboard" replace />} />
          </Routes>
        </ProtectedRoute>
      } />

      <Route path="/help" element={<UserGuide />} />
      <Route path="/user-guide" element={<ProtectedRoute><UserGuide /></ProtectedRoute>} />
      <Route path="/superadmin/guide" element={<ProtectedRoute allowedRoles={["superadmin"]}><UserGuide allowDownloads /></ProtectedRoute>} />
      <Route path="/school-preview" element={<Login preview />} />
      <Route path="/payments/return" element={<PaymentReturn />} />
      <Route path="/superadmin/appearance" element={<ProtectedRoute allowedRoles={["superadmin"]}><PortalDesigns /></ProtectedRoute>} />
      <Route path="/superadmin/payments" element={<ProtectedRoute allowedRoles={["superadmin"]}><PlatformPayments /></ProtectedRoute>} />
      <Route path="/superadmin/team" element={<ProtectedRoute allowedRoles={["superadmin"]}><PlatformTeam /></ProtectedRoute>} />
      <Route path="/superadmin/dashboard" element={
        <ProtectedRoute allowedRoles={["superadmin"]}>
          <PlatformDashboard />
        </ProtectedRoute>
      } />
      <Route path="/"  element={<RootRedirect />} />
      <Route path="*"  element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <PortalNavigation><AppRoutes /></PortalNavigation>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}
