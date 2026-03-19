"""
accounts/permissions.py

DRF permission classes for role-based access control.

Every permission checks TWO things:
  1. The user's role matches the required role.
  2. The user belongs to the current request tenant (school).
     Exception: IsSuperAdmin has no school constraint.

Usage in ViewSets:
    class StudentViewSet(TenantMixin, viewsets.ModelViewSet):
        permission_classes = [IsSchoolAdmin | IsTeacher]
"""

from rest_framework.permissions import BasePermission, IsAuthenticated


class _RolePermission(BasePermission):
    """
    Abstract base: subclasses define `allowed_roles`.
    Checks authentication + role membership.
    """

    allowed_roles: tuple = ()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in self.allowed_roles


class _TenantRolePermission(_RolePermission):
    """
    Like _RolePermission but also enforces that the user's school
    matches request.tenant (prevents cross-school access).
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        tenant = getattr(request, "tenant", None)

        # No tenant on the request — middleware didn't resolve one.
        # Deny tenant-scoped roles; they must operate within a school.
        if tenant is None:
            return False

        return request.user.school_id == tenant.pk


# ── Concrete permission classes ───────────────────────────────────────────────


class IsSuperAdmin(_RolePermission):
    """
    Platform-level superadmin only.
    NOT tenant-scoped — superadmin can act across all schools.
    """
    allowed_roles = ("superadmin",)
    message = "Only platform superadmins can perform this action."


class IsSchoolAdmin(_TenantRolePermission):
    """School admin for the current tenant."""
    allowed_roles = ("school_admin",)
    message = "Only school administrators can perform this action."


class IsTeacher(_TenantRolePermission):
    """Teacher for the current tenant."""
    allowed_roles = ("teacher",)
    message = "Only teachers can perform this action."


class IsStudent(_TenantRolePermission):
    """Student for the current tenant."""
    allowed_roles = ("student",)
    message = "Only students can perform this action."


class IsParent(_TenantRolePermission):
    """Parent for the current tenant."""
    allowed_roles = ("parent",)
    message = "Only parents can perform this action."


# ── Composite helpers (use with | operator in permission_classes) ─────────────

class IsSchoolAdminOrTeacher(_TenantRolePermission):
    """School admin or teacher — common for content management."""
    allowed_roles = ("school_admin", "teacher")
    message = "School admins and teachers can perform this action."


class IsSchoolStaff(_TenantRolePermission):
    """Any staff member of the school (admin or teacher)."""
    allowed_roles = ("school_admin", "teacher")
    message = "Only school staff can perform this action."


class IsAuthenticatedTenantUser(IsAuthenticated):
    """
    Any authenticated user who belongs to the current tenant.
    Use as a base for endpoints all logged-in users can access
    (e.g., GET /api/auth/me/).
    """

    message = "You must be logged in to a valid school subdomain."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        tenant = getattr(request, "tenant", None)

        # Superadmins are not tenant-bound
        if request.user.role == "superadmin":
            return True

        if tenant is None:
            return False

        return request.user.school_id == tenant.pk