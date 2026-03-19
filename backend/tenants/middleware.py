"""
tenants/middleware.py

TenantMiddleware — resolves the current School tenant from the request subdomain
and attaches it to `request.tenant`.

Flow:
  1. Extract subdomain from Host header.
  2. Skip middleware for exempt paths (superadmin, health, auth).
  3. Look up School by subdomain.
  4. Attach school to request or return 404 JSON.
"""

import json

from django.http import JsonResponse

from .models import School


# Paths where tenant resolution is NOT required.
EXEMPT_PATH_PREFIXES = (
    "/superadmin/",
    "/health/",
    "/api/auth/",
)


class TenantMiddleware:
    """
    Middleware that identifies the tenant (School) from the request subdomain.

    Place this AFTER SecurityMiddleware in MIDDLEWARE settings.

    After this middleware runs, all subsequent code can safely access
    `request.tenant` to get the current School instance.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ── 1. Skip exempt paths ──────────────────────────────────────────────
        if self._is_exempt(request.path):
            request.tenant = None
            return self.get_response(request)

        # ── 2. Extract subdomain from Host header ─────────────────────────────
        subdomain = self._extract_subdomain(request)

        if not subdomain:
            # Request came from the bare apex domain (no subdomain).
            # Allow it through without a tenant — views can decide what to do.
            request.tenant = None
            return self.get_response(request)

        # ── 3. Resolve School from subdomain ──────────────────────────────────
        try:
            school = School.objects.get(subdomain=subdomain, is_active=True)
        except School.DoesNotExist:
            return JsonResponse(
                {
                    "error": "School not found",
                    "detail": (
                        f"No active school is registered for subdomain '{subdomain}'. "
                        "Please check the URL or contact support."
                    ),
                },
                status=404,
            )

        # ── 4. Attach tenant to request ───────────────────────────────────────
        request.tenant = school

        return self.get_response(request)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _is_exempt(self, path: str) -> bool:
        """Return True if the path should skip tenant resolution."""
        return any(path.startswith(prefix) for prefix in EXEMPT_PATH_PREFIXES)

    def _extract_subdomain(self, request) -> str | None:
        """
        Parse the subdomain from the Host header.

        Examples:
          greenfield.myplatform.com  →  "greenfield"
          myplatform.com             →  None
          localhost:8000             →  None  (local dev, no subdomain)
          greenfield.localhost:8000  →  "greenfield"
        """
        host = request.get_host().lower()

        # Strip port number if present (e.g. localhost:8000)
        host = host.split(":")[0]

        parts = host.split(".")

        # A subdomain exists when there are more than 2 parts
        # e.g. ["greenfield", "myplatform", "com"]  → len == 3
        # e.g. ["myplatform", "com"]               → len == 2  (no subdomain)
        # e.g. ["greenfield", "localhost"]          → len == 2  (dev subdomain)
        if len(parts) >= 3:
            return parts[0]

        # Support local dev: greenfield.localhost
        if len(parts) == 2 and parts[1] in ("localhost", "test"):
            return parts[0]

        return None