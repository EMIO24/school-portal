/**
 * utils/roles.js
 *
 * Role constants and dashboard route map.
 * Single source of truth — used by AuthContext, ProtectedRoute, and Login.
 */

export const ROLES = {
  SUPERADMIN:   "superadmin",
  SCHOOL_ADMIN: "school_admin",
  TEACHER:      "teacher",
  STUDENT:      "student",
  PARENT:       "parent",
};

/** Maps a role to its home dashboard route */
export const ROLE_DASHBOARDS = {
  superadmin:   "/superadmin/dashboard",
  school_admin: "/admin/dashboard",
  teacher:      "/teacher/dashboard",
  student:      "/student/dashboard",
  parent:       "/parent/dashboard",
};

/** Human-readable role labels */
export const ROLE_LABELS = {
  superadmin:   "Super Admin",
  school_admin: "School Admin",
  teacher:      "Teacher",
  student:      "Student",
  parent:       "Parent",
};