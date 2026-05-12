from django.urls import path
from .views import (
    NotificationSendView,
    NotificationLogListView,
    NotificationTemplateListView,
    NotificationTemplateDetailView,
)

urlpatterns = [
    path('send/',               NotificationSendView.as_view()),
    path('logs/',               NotificationLogListView.as_view()),
    path('templates/',          NotificationTemplateListView.as_view()),
    path('templates/<int:pk>/', NotificationTemplateDetailView.as_view()),
]
