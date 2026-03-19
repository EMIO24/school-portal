"""
accounts/urls.py

Auth endpoints — all exempt from TenantMiddleware via the
/api/auth/ prefix configured in tenants/middleware.py.
"""

from django.urls import path

from .views import ChangePasswordView, LoginView, MeView, TokenRefreshView

urlpatterns = [
    # ── Authentication ────────────────────────────────────────────────────────
    path("login/",         LoginView.as_view(),          name="auth-login"),
    path("token/refresh/", TokenRefreshView.as_view(),   name="auth-token-refresh"),

    # ── Authenticated user ────────────────────────────────────────────────────
    path("me/",            MeView.as_view(),             name="auth-me"),
    path("change-password/", ChangePasswordView.as_view(), name="auth-change-password"),
]