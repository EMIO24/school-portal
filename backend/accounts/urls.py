"""
accounts/urls.py

Auth endpoints — all exempt from TenantMiddleware via the
/api/auth/ prefix configured in tenants/middleware.py.
"""

from django.urls import path

from .views import (
    ChangePasswordView, LoginView, MeView, TokenRefreshView,
    ParentOTPRequestView, ParentOTPVerifyView,
)

urlpatterns = [
    # ── Authentication ────────────────────────────────────────────────────────
    path("login/",         LoginView.as_view(),          name="auth-login"),
    path("token/refresh/", TokenRefreshView.as_view(),   name="auth-token-refresh"),

    # ── Authenticated user ────────────────────────────────────────────────────
    path("me/",            MeView.as_view(),             name="auth-me"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),

    # ── Parent OTP login (public — must stay under /api/auth/ exempt prefix) ──
    path("parent/otp-request/", ParentOTPRequestView.as_view(), name="parent-otp-request"),
    path("parent/otp-verify/",  ParentOTPVerifyView.as_view(),  name="parent-otp-verify"),

    # Parent data views live at /api/parent/ (see accounts/parent_urls.py)
    # so that TenantMiddleware resolves request.tenant before they run.
]