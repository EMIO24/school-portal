from django.urls import path
from .views import PlanView, TopicView, LessonCurriculumView, CoverageView, ScheduledCurriculumView, AssignedPlansView

urlpatterns = [
    path('assignments/', AssignedPlansView.as_view()),
    path('plans/', PlanView.as_view()),
    path('topics/<int:topic_id>/', TopicView.as_view()),
    path('lessons/<int:lesson_id>/', LessonCurriculumView.as_view()),
    path('slots/<int:slot_id>/', ScheduledCurriculumView.as_view()),
    path('lessons/<int:lesson_id>/topics/<int:topic_id>/', CoverageView.as_view()),
]
