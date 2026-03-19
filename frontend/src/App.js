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
import Login          from "./pages/public/Login";
import ChangePassword from "./pages/public/ChangePassword";

// ── Admin pages ────────────────────────────────────────────────────────────
import AdminDashboard   from "./pages/admin/AdminDashboard";
import CalendarSettings from "./pages/admin/CalendarSettings";
import Students         from "./pages/admin/Students";
import StudentForm      from "./pages/admin/StudentForm";
import StudentProfilePage from "./pages/admin/StudentProfile";
import Staff            from "./pages/admin/Staff";
import StaffForm        from "./pages/admin/StaffForm";
import StaffProfilePage from "./pages/admin/StaffProfilePage";
import BulkImportPage   from "./pages/admin/BulkImportPage";

// ── Role dashboards (stubs) ────────────────────────────────────────────────
import TeacherDashboard from "./pages/teacher/TeacherDashboard";
import StudentDashboard from "./pages/student/StudentDashboard";
import ParentDashboard  from "./pages/parent/ParentDashboard";

// ── Helpers ────────────────────────────────────────────────────────────────
import { useAuth } from "./hooks/useAuth";
import { ROLE_DASHBOARDS } from "./utils/roles";
import LoadingScreen from "./components/common/LoadingScreen";

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
      <Route path="/login"           element={<Login />} />
      <Route path="/change-password" element={
        <ProtectedRoute><ChangePassword /></ProtectedRoute>
      } />

      {/* ── School Admin ─────────────────────────────────────────────────── */}
      <Route path="/admin/*" element={
        <ProtectedRoute allowedRoles={["school_admin"]}>
          <Routes>
            <Route path="dashboard"            element={<AdminDashboard />} />

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

            {/*
              Upcoming admin routes (added in later prompts):
              <Route path="subjects"           element={<Subjects />} />
              <Route path="results"            element={<ResultsManager />} />
              <Route path="cbt"                element={<CBTManager />} />
              <Route path="fees"               element={<FeeManager />} />
              <Route path="settings"           element={<SchoolSettings />} />
            */}
            <Route index element={<Navigate to="dashboard" replace />} />
          </Routes>
        </ProtectedRoute>
      } />

      {/* ── Teacher ──────────────────────────────────────────────────────── */}
      <Route path="/teacher/*" element={
        <ProtectedRoute allowedRoles={["teacher"]}>
          <Routes>
            <Route path="dashboard" element={<TeacherDashboard />} />
            {/*
              Upcoming teacher routes:
              <Route path="classes"      element={<MyClasses />} />
              <Route path="attendance"   element={<Attendance />} />
              <Route path="scores"       element={<ScoreEntry />} />
              <Route path="cbt"          element={<CBTManage />} />
            */}
            <Route index element={<Navigate to="dashboard" replace />} />
          </Routes>
        </ProtectedRoute>
      } />

      {/* ── Student ──────────────────────────────────────────────────────── */}
      <Route path="/student/*" element={
        <ProtectedRoute allowedRoles={["student"]}>
          <Routes>
            <Route path="dashboard" element={<StudentDashboard />} />
            {/*
              Upcoming student routes:
              <Route path="results"    element={<MyResults />} />
              <Route path="cbt"        element={<CBTExam />} />
              <Route path="timetable"  element={<Timetable />} />
              <Route path="profile"    element={<StudentSelfProfile />} />
            */}
            <Route index element={<Navigate to="dashboard" replace />} />
          </Routes>
        </ProtectedRoute>
      } />

      {/* ── Parent ───────────────────────────────────────────────────────── */}
      <Route path="/parent/*" element={
        <ProtectedRoute allowedRoles={["parent"]}>
          <Routes>
            <Route path="dashboard" element={<ParentDashboard />} />
            {/*
              Upcoming parent routes:
              <Route path="children"   element={<MyChildren />} />
              <Route path="results"    element={<ChildResults />} />
              <Route path="fees"       element={<FeeStatus />} />
            */}
            <Route index element={<Navigate to="dashboard" replace />} />
          </Routes>
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
          <AppRoutes />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}