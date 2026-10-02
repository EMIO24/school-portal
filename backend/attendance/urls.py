"""
backend/attendance/urls.py
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (AttendanceSessionViewSet, StudentClockOutView, StudentPresenceCorrectionView,
                    StudentPresenceSettingsView, StudentPresenceView)

router = DefaultRouter()
router.register(r'sessions', AttendanceSessionViewSet, basename='attendance-session')

urlpatterns = [
    path('presence/', StudentPresenceView.as_view()),
    path('presence/clock-out/', StudentClockOutView.as_view()),
    path('presence/settings/', StudentPresenceSettingsView.as_view()),
    path('presence/<int:pk>/correct/', StudentPresenceCorrectionView.as_view()),
    path('', include(router.urls)),
]

# ─── Endpoint reference ───────────────────────────────────────────────────────
#
# POST   /api/attendance/sessions/start/
# GET    /api/attendance/sessions/{id}/
# PATCH  /api/attendance/sessions/{id}/submit/
# PATCH  /api/attendance/sessions/{id}/finalize/
# GET    /api/attendance/sessions/report/?student=&term=
# GET    /api/attendance/sessions/class-report/?class_arm=&term=
# GET    /api/attendance/sessions/class-report/?class_arm=&term=&format=csv
# GET    /api/attendance/sessions/low-attendance/?term=&threshold=75