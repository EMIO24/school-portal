"""
config/urls.py — complete root URL configuration
"""

from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse
from results.urls import results_urlpatterns, scratch_card_urlpatterns


def health_check(request):
    return JsonResponse({"status": "ok", "version": "1.0"})


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

    path('api/attendance/',    include('attendance.urls')),
    path('api/gradebook/',     include('gradebook.urls')),
    path('api/cbt/',           include('cbt.urls')),
    path('api/results/',       include((results_urlpatterns,      'results'))),
    path('api/scratch-cards/', include((scratch_card_urlpatterns, 'scratch-cards'))),

    # Phase 4
    path('api/notifications/', include('notifications.urls')),
    path('api/fees/',          include('fees.urls')),

    # Timetable
    path('api/timetable/',     include('timetable.urls')),

    # Parent data (tenant-aware — must NOT be under /api/auth/)
    path('api/parent/',        include('accounts.parent_urls')),

    # Phase 5
    path('api/analytics/',     include('analytics.urls')),
    path('api/reports/',       include('analytics.reports_urls')),  # transcript only
    path('api/promotion/',     include('promotion.urls')),
]