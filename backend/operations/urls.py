from django.urls import path

from .views import (
    AdmissionApplicationListCreate,
    AdmissionApplicationDetail,
    AdmissionDecisionView,
    AdmissionDocumentCreate,
    StudentRecordListCreate,
    WelfareCaseListCreate,
    WelfareCaseDetail,
    WelfareCaseUpdateView,
)

urlpatterns = [
    path("admissions/", AdmissionApplicationListCreate.as_view()),
    path("admissions/<int:pk>/", AdmissionApplicationDetail.as_view()),
    path("admissions/<int:pk>/decision/", AdmissionDecisionView.as_view()),
    path("admissions/<int:pk>/documents/", AdmissionDocumentCreate.as_view()),
    path("student-records/<int:student_id>/", StudentRecordListCreate.as_view()),
    path("welfare/", WelfareCaseListCreate.as_view()),
    path("welfare/<int:pk>/", WelfareCaseDetail.as_view()),
    path("welfare/<int:pk>/updates/", WelfareCaseUpdateView.as_view()),
]
