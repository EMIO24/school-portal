"""
config/urls.py — complete root URL configuration
"""

from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    # Django admin — exempt from TenantMiddleware via /superadmin/ prefix
    path("superadmin/", admin.site.urls),

    # Health probe — exempt from TenantMiddleware
    path("health/", health_check),

    # Auth — exempt from TenantMiddleware via /api/auth/ prefix
    path("api/auth/", include("accounts.urls")),

    # Tenants (school onboarding + school/me)
    path("api/", include("tenants.urls")),

    # Academic calendar (sessions, terms, holidays)
    path("api/", include("academics.urls")),

    # Enrollment (students, staff, class levels/arms, subjects)
    path("api/", include("enrollment.urls")),

    path('api/attendance/', include('attendance.urls')),
]