"""
backend/attendance/urls.py
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AttendanceSessionViewSet
from .student_views import MyAttendanceRecordsView

router = DefaultRouter()
router.register(r'sessions', AttendanceSessionViewSet, basename='attendance-session')

urlpatterns = [
    path('my-records/', MyAttendanceRecordsView.as_view(), name='my-attendance-records'),
    path('', include(router.urls)),
]

# ─── Endpoint reference ───────────────────────────────────────────────────────
#
# GET    /api/attendance/my-records/?term=        logged-in student's records
# POST   /api/attendance/sessions/start/
# GET    /api/attendance/sessions/{id}/
# PATCH  /api/attendance/sessions/{id}/submit/
# PATCH  /api/attendance/sessions/{id}/finalize/
# GET    /api/attendance/sessions/report/?student=&term=
# GET    /api/attendance/sessions/class-report/?class_arm=&term=
# GET    /api/attendance/sessions/class-report/?class_arm=&term=&format=csv
# GET    /api/attendance/sessions/low-attendance/?term=&threshold=75
