/**
 * components/common/ProtectedRoute.jsx
 *
 * Guards routes by authentication status and role.
 *
 * Usage:
 *   <ProtectedRoute allowedRoles={['teacher', 'school_admin']}>
 *     <TeacherDashboard />
 *   </ProtectedRoute>
 *
 * Behaviour:
 *   - Not authenticated   → redirect to /login (preserves intended destination)
 *   - Wrong role          → redirect to user's own dashboard
 *   - isLoading           → show full-page spinner (avoids flash redirect)
 *   - Correct role        → render children
 */

import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { ROLE_DASHBOARDS } from "../../utils/roles";
import LoadingScreen from "./LoadingScreen";

/**
 * @param {string[]} allowedRoles  — roles that may access this route.
 *                                   Empty / undefined = any authenticated user.
 * @param {React.ReactNode} children
 */
export default function ProtectedRoute({ allowedRoles = [], children }) {
  const { isAuthenticated, isLoading, user } = useAuth();
  const location = useLocation();

  // ── Still resolving persisted session ────────────────────────────────────
  if (isLoading) {
    return <LoadingScreen />;
  }

  // ── Not logged in ─────────────────────────────────────────────────────────
  if (!isAuthenticated || !user) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname }} // LoginPage reads this to redirect back
      />
    );
  }

  // ── Role check ────────────────────────────────────────────────────────────
  if (allowedRoles.length > 0 && !allowedRoles.includes(user.role)) {
    const ownDashboard = ROLE_DASHBOARDS[user.role] || "/";
    return <Navigate to={ownDashboard} replace />;
  }

  return children;
}