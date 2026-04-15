"""
backend/cbt/urls.py

Endpoint reference:
  GET/POST          /api/cbt/topics/
  GET/PUT/PATCH/DELETE /api/cbt/topics/{id}/
  GET/POST          /api/cbt/questions/
  GET/PUT/PATCH/DELETE /api/cbt/questions/{id}/
  GET               /api/cbt/questions/stats/
  POST              /api/cbt/questions/bulk-import/
"""
from rest_framework.routers import DefaultRouter
from .views import TopicViewSet, QuestionViewSet

router = DefaultRouter()
router.register('topics',    TopicViewSet,   basename='topic')
router.register('questions', QuestionViewSet, basename='question')

urlpatterns = router.urls
