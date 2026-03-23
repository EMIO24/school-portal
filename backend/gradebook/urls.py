"""
backend/gradebook/urls.py
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ScoreEntryViewSet, AffectiveDomainViewSet, PsychomotorDomainViewSet

router = DefaultRouter()
router.register(r'entries',     ScoreEntryViewSet,      basename='score-entry')
router.register(r'affective',   AffectiveDomainViewSet, basename='affective')
router.register(r'psychomotor', PsychomotorDomainViewSet, basename='psychomotor')

urlpatterns = [path('', include(router.urls))]

# ─── Endpoint reference ───────────────────────────────────────────────────────
# GET    /api/gradebook/entries/?class_arm=&subject=&term=
# POST   /api/gradebook/entries/bulk-update/
# POST   /api/gradebook/entries/publish/?class_arm=&subject=&term=
# GET    /api/gradebook/entries/grade-scale/
# GET    /api/gradebook/affective/?class_arm=&term=
# GET/PUT /api/gradebook/affective/student/{id}/term/{id}/
# GET    /api/gradebook/psychomotor/?class_arm=&term=
# GET/PUT /api/gradebook/psychomotor/student/{id}/term/{id}/