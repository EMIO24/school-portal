"""
tenants/urls.py

URL configuration for the tenants app.

Registered in config/urls.py as:
    path("api/", include("tenants.urls"))
"""

from django.urls import path

from .views import SchoolDetailView, SchoolMeView, SchoolOnboardingView

urlpatterns = [
    # SuperAdmin: list all schools / create a school
    path("schools/", SchoolOnboardingView.as_view(), name="school-list-create"),

    # SuperAdmin: retrieve / update a specific school
    path("schools/<int:pk>/", SchoolDetailView.as_view(), name="school-detail"),

    # Public: returns branding info for the current subdomain tenant
    path("school/me/", SchoolMeView.as_view(), name="school-me"),
]