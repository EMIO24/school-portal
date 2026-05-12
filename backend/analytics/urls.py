from django.urls import path
from .views import (
    AnalyticsOverviewView, AnalyticsRefreshView,
    ClassAnalyticsView, StudentTrendsView, TranscriptPDFView,
)

urlpatterns = [
    path('overview/',                    AnalyticsOverviewView.as_view()),
    path('refresh/',                     AnalyticsRefreshView.as_view()),
    path('class/<int:pk>/',              ClassAnalyticsView.as_view()),
    path('student/<int:pk>/trends/',     StudentTrendsView.as_view()),
    path('transcript/<int:pk>/',         TranscriptPDFView.as_view()),
]
