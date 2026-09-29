from django.urls import path
from .views import PlanView, TopicView, LessonCurriculumView, CoverageView, ScheduledCurriculumView, AssignedPlansView
from .standards import (
    CurriculumSourceListView, CurriculumVersionCreateView, CurriculumApplicabilityView,
    AcademicStandardListView, AcademicStandardDetailView, AcademicStandardTopicCreateView,
    AcademicStandardTransitionView, AcademicStandardReviseView, AcademicStandardGeneratePlanView,
)
from .learning import (
    LessonPlanListView, LessonPlanTransitionView,
    AcademicResourceListView, AcademicResourceTransitionView, AcademicResourceReviseView,
)

urlpatterns = [
    path('standards/sources/', CurriculumSourceListView.as_view()),
    path('standards/sources/<int:source_id>/versions/', CurriculumVersionCreateView.as_view()),
    path('standards/applicability/', CurriculumApplicabilityView.as_view()),
    path('standards/', AcademicStandardListView.as_view()),
    path('standards/<int:standard_id>/', AcademicStandardDetailView.as_view()),
    path('standards/<int:standard_id>/topics/', AcademicStandardTopicCreateView.as_view()),
    path('standards/<int:standard_id>/transition/', AcademicStandardTransitionView.as_view()),
    path('standards/<int:standard_id>/revise/', AcademicStandardReviseView.as_view()),
    path('standards/<int:standard_id>/generate-plan/', AcademicStandardGeneratePlanView.as_view()),
    path('lesson-plans/', LessonPlanListView.as_view()),
    path('lesson-plans/<int:plan_id>/transition/', LessonPlanTransitionView.as_view()),
    path('resources/', AcademicResourceListView.as_view()),
    path('resources/<int:resource_id>/transition/', AcademicResourceTransitionView.as_view()),
    path('resources/<int:resource_id>/revise/', AcademicResourceReviseView.as_view()),
    path('assignments/', AssignedPlansView.as_view()),
    path('plans/', PlanView.as_view()),
    path('topics/<int:topic_id>/', TopicView.as_view()),
    path('lessons/<int:lesson_id>/', LessonCurriculumView.as_view()),
    path('slots/<int:slot_id>/', ScheduledCurriculumView.as_view()),
    path('lessons/<int:lesson_id>/topics/<int:topic_id>/', CoverageView.as_view()),
]
