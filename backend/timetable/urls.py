"""
backend/timetable/urls.py

Register both ViewSets with the DRF DefaultRouter.

Add to root urls.py:
    path('api/timetable/', include('timetable.urls')),
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PeriodViewSet, TimetableEntryViewSet
from .teaching import LessonDayView, LessonOutcomeView

router = DefaultRouter()
router.register(r'periods', PeriodViewSet,        basename='period')
router.register(r'entries', TimetableEntryViewSet, basename='timetable-entry')

urlpatterns = [
    path('lessons/', LessonDayView.as_view(), name='lesson-day'),
    path('lessons/<int:slot_id>/<str:lesson_date>/', LessonOutcomeView.as_view(), name='lesson-outcome'),
    path('', include(router.urls)),
]

# ─── Generated endpoint reference ────────────────────────────────────────────
#
# GET    /api/timetable/periods/
# POST   /api/timetable/periods/
# GET    /api/timetable/periods/{id}/
# PATCH  /api/timetable/periods/{id}/
# DELETE /api/timetable/periods/{id}/
#
# GET    /api/timetable/entries/
# POST   /api/timetable/entries/
# GET    /api/timetable/entries/{id}/
# PATCH  /api/timetable/entries/{id}/
# DELETE /api/timetable/entries/{id}/
#
# GET    /api/timetable/entries/grid/?class_arm=<id>&term=<id>
# GET    /api/timetable/entries/by-class/<id>/?term=<id>
# GET    /api/timetable/entries/by-teacher/<id>/?term=<id>
# GET    /api/timetable/entries/my-timetable/?term=<id>
# GET    /api/timetable/entries/teacher-load/?teacher=<id>&term=<id>
