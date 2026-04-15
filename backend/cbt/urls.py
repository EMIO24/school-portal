"""
backend/cbt/urls.py

Endpoint reference:
  GET/POST             /api/cbt/topics/
  GET/PUT/PATCH/DELETE /api/cbt/topics/{id}/
  GET/POST             /api/cbt/questions/
  GET/PUT/PATCH/DELETE /api/cbt/questions/{id}/
  GET                  /api/cbt/questions/stats/
  POST                 /api/cbt/questions/bulk-import/
  GET/POST             /api/cbt/exams/
  GET/PUT/PATCH/DELETE /api/cbt/exams/{id}/
  GET                  /api/cbt/exams/available/
  POST                 /api/cbt/exams/{id}/start/
  POST                 /api/cbt/exams/{id}/save-answer/
  GET                  /api/cbt/exams/{id}/status/
  POST                 /api/cbt/exams/{id}/submit/
  POST                 /api/cbt/exams/{id}/log-tab-switch/
"""
from rest_framework.routers import DefaultRouter
from .views import TopicViewSet, QuestionViewSet, CBTExamViewSet

router = DefaultRouter()
router.register('topics',    TopicViewSet,    basename='topic')
router.register('questions', QuestionViewSet, basename='question')
router.register('exams',     CBTExamViewSet,  basename='exam')

urlpatterns = router.urls
