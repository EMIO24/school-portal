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
  if (user.role !== 'superadmin' && !hasFeature(school, feature)) {
    const title = school?.entitlements?.labels?.[feature] || 'This feature';
    const upgradeCopy = {
      cbt: {
        title: 'Computer-Based Testing',
        headline: 'CBT is available with Paideia Premium.',
        description: 'Upgrade to Premium to create examinations, manage question banks, automatically mark objective tests and analyse examination performance.',
        cta: 'View Premium Features',
        to: '/admin/subscription',
      },
      analytics: {
        title: 'Advanced Analytics',
        headline: 'Advanced Analytics is available with Paideia Premium.',
        description: 'Upgrade to Premium to unlock dashboards, cohort insights and performance trends across your school.',
        cta: 'View Premium Features',
        to: '/admin/subscription',
      },
      notifications: {
        title: 'Notifications',
        headline: 'Notifications is available with Paideia Premium.',
        description: 'Upgrade to Premium to send announcements, reminders and parent updates automatically.',
        cta: 'View Premium Features',
        to: '/admin/subscription',
      },
    };
    const copy = upgradeCopy[feature] || {
      title,
      headline: `${title} is available on an upgraded plan.`,
      description: 'Upgrade your school plan to unlock this feature and keep your operations moving.',
      cta: 'View Premium Features',
      to: '/admin/subscription',
    };

    return (
      <main className="plan-locked">
        <span className="workspace-eyebrow">Your school plan</span>
        <h1>{copy.title}</h1>
        <p>{copy.headline}</p>
        <p>{copy.description}</p>
        {user.role === 'school_admin' ? <Link className="workspace-action" to={copy.to}>{copy.cta}</Link> : <p>Ask your school administrator about enabling this feature.</p>}
        <p><Link to={ROLE_DASHBOARDS[user.role]}>Back to dashboard</Link></p>
      </main>
    );
  }
  return children;
}