"""
accounts/parent_urls.py

Tenant-aware parent data endpoints.
Mounted at /api/parent/ (NOT under /api/auth/) so TenantMiddleware resolves
request.tenant before these views run.
"""

from django.urls import path

from .views import ParentChildrenView, ParentStudentDashboardView

urlpatterns = [
    path("children/",              ParentChildrenView.as_view(),         name="parent-children"),
    path("dashboard/<int:pk>/",    ParentStudentDashboardView.as_view(), name="parent-dashboard"),
]
