"""
academics/urls.py

Registered in config/urls.py as:
    path("api/", include("academics.urls"))
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CurrentCalendarView, HolidayViewSet, SessionViewSet, TermViewSet

router = DefaultRouter()
router.register(r"sessions",  SessionViewSet,       basename="session")
router.register(r"terms",     TermViewSet,          basename="term")
router.register(r"holidays",  HolidayViewSet,       basename="holiday")
router.register(r"calendar",  CurrentCalendarView,  basename="calendar")

urlpatterns = [
    path("", include(router.urls)),
]

# Routes generated:
#   GET/POST   /api/sessions/
#   GET/PUT/PATCH/DELETE  /api/sessions/{id}/
#   POST       /api/sessions/{id}/set-current/
#   GET/POST   /api/terms/
#   GET/PUT/PATCH/DELETE  /api/terms/{id}/
#   POST       /api/terms/{id}/set-current/
#   GET/POST   /api/holidays/
#   GET        /api/calendar/          ← CurrentCalendarView.list()