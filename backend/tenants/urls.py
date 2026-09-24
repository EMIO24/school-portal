"""
tenants/urls.py

URL configuration for the tenants app.

Registered in config/urls.py as:
    path("api/", include("tenants.urls"))
"""

from django.urls import path

from .views import SchoolDetailView, SchoolLookupView, SchoolMeView, SchoolOnboardingView

urlpatterns = [
    # SuperAdmin: list all schools / create a school
    path("schools/", SchoolOnboardingView.as_view(), name="school-list-create"),

    # SuperAdmin: retrieve / update a specific school
    path("schools/<int:pk>/", SchoolDetailView.as_view(), name="school-detail"),

    # Public: returns branding info for the current subdomain tenant
    path("school/me/", SchoolMeView.as_view(), name="school-me"),
    path("school-lookup/", SchoolLookupView.as_view(), name="school-lookup"),
]

from .platform import SchoolRegistration, PlatformSchools, PlatformSchoolDetail, PlatformSchoolLogo, PlatformAdministrators, PlatformProfile, DemoRequestView, PlatformDemoRequests
urlpatterns += [
    path("platform/me/", PlatformProfile.as_view()),
    path("platform/register/", SchoolRegistration.as_view()),
    path("platform/schools/", PlatformSchools.as_view()),
    path("platform/schools/<int:pk>/", PlatformSchoolDetail.as_view()),
    path("platform/schools/<int:pk>/logo/", PlatformSchoolLogo.as_view()),
    path("platform/schools/<int:pk>/administrators/", PlatformAdministrators.as_view()),
    path("demo-requests/", DemoRequestView.as_view()),
    path("platform/demo-requests/", PlatformDemoRequests.as_view()),
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

from fees.exceptions import PlatformPaymentExceptions
from fees.invoice_views import OwnerInvoices
urlpatterns += [path('platform/invoices/', OwnerInvoices.as_view()),
                path('platform/invoices/<int:pk>/', OwnerInvoices.as_view())]
urlpatterns += [path('platform/payment-exceptions/', PlatformPaymentExceptions.as_view()),
                path('platform/payment-exceptions/<int:pk>/', PlatformPaymentExceptions.as_view())]
