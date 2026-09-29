import { useTheme } from "../../context/ThemeContext";
import { featureForRoute, hasFeature } from "../../services/features";
import { Link } from "react-router-dom";
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
  const { school } = useTheme();

  // ── Still resolving persisted session ────────────────────────────────────
  if (isLoading) {
    return <LoadingScreen />;
  }

  // ── Not logged in ─────────────────────────────────────────────────────────
  if (!isAuthenticated || !user) {
    return (
      <Navigate
        to={allowedRoles.length === 1 && allowedRoles[0] === "superadmin" ? "/platform/login" : "/login"}
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

  if (user.role === "superadmin" && user.mustChangePassword && location.pathname !== "/platform/change-password") {
    return <Navigate to="/platform/change-password" replace />;
  }

  const feature = featureForRoute(location.pathname);
  if (user.role !== 'superadmin' && !hasFeature(school, feature)) return <main className="plan-locked"><span className="workspace-eyebrow">Your school plan</span><h1>More possibilities for your school</h1><p>{school.entitlements.labels?.[feature] || 'This feature'} is available on an upgraded plan.</p>{user.role === 'school_admin' ? <Link className="workspace-action" to="/admin/subscription">Compare plans</Link> : <p>Ask your school administrator about enabling this feature.</p>}<p><Link to={ROLE_DASHBOARDS[user.role]}>Back to dashboard</Link></p></main>;
  return children;
}