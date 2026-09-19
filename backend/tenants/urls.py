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

from .platform import SchoolRegistration, PlatformSchools, PlatformSchoolDetail, PlatformAdministrators, PlatformProfile
urlpatterns += [
    path("platform/me/", PlatformProfile.as_view()),
    path("platform/register/", SchoolRegistration.as_view()),
    path("platform/schools/", PlatformSchools.as_view()),
    path("platform/schools/<int:pk>/", PlatformSchoolDetail.as_view()),
    path("platform/schools/<int:pk>/administrators/", PlatformAdministrators.as_view()),
]

from .security import VerifyMFA
urlpatterns += [path("platform/auth/verify/", VerifyMFA.as_view())]

from .platform import PlatformAccounts, PlatformAudit
urlpatterns += [path("platform/accounts/", PlatformAccounts.as_view()), path("platform/audit/", PlatformAudit.as_view())]

from .platform import PlatformPassword
urlpatterns += [path("platform/password/", PlatformPassword.as_view())]

from fees.payments import PaystackWebhook, PlatformPayments, PlatformPaymentAccount
urlpatterns += [path('platform/paystack/webhook/', PaystackWebhook.as_view()), path('platform/payments/', PlatformPayments.as_view()), path('platform/schools/<int:pk>/payments/', PlatformPaymentAccount.as_view())]

from .platform import PlatformAppearance
urlpatterns += [path("platform/appearance/", PlatformAppearance.as_view())]
