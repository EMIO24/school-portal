from django.urls import path
from .views import TranscriptPDFView

urlpatterns = [
    path('transcript/<int:pk>/', TranscriptPDFView.as_view()),
]
