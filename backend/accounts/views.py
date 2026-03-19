"""
accounts/views.py

Authentication views for the school portal.

All paths under /api/auth/ are exempt from TenantMiddleware
(configured in middleware.py) so login works before tenant resolves.
Tenant validation happens INSIDE LoginView instead.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenRefreshView  # re-exported below

from tenants.serializers import SchoolPublicSerializer

from .permissions import IsAuthenticatedTenantUser
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    UserProfileSerializer,
)


class LoginView(APIView):
    """
    POST /api/auth/login/

    Request body:
        { "email": "...", "password": "..." }

    Response (200):
        {
            "access":               "<JWT access token>",
            "refresh":              "<JWT refresh token>",
            "role":                 "student",
            "must_change_password": false,
            "user":                 { ...UserProfileSerializer fields },
            "theme":                { ...school theme }
        }

    The frontend should:
      1. Store access + refresh in memory / secure storage.
      2. If must_change_password == true → redirect to /change-password.
      3. Inject theme into CSS variables (ThemeProvider handles this).
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})

        if not serializer.is_valid():
            return Response(
                {"errors": serializer.errors},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user   = serializer.validated_data["user"]
        tokens = serializer.get_tokens(user)

        # Build theme from the user's school (None for superadmin)
        theme = None
        if user.school:
            theme = SchoolPublicSerializer(user.school).data

        return Response(
            {
                **tokens,                                   # access + refresh
                "role":                 user.role,
                "must_change_password": user.must_change_password,
                "user":                 UserProfileSerializer(user).data,
                "theme":                theme,
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    GET /api/auth/me/

    Returns the profile of the currently authenticated user.
    Requires a valid JWT in the Authorization header.
    """

    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        """
        PATCH /api/auth/me/

        Update editable profile fields (first_name, last_name,
        phone_number, profile_photo). Email and role are read-only.
        """
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """
    POST /api/auth/change-password/

    Request body:
        {
            "current_password": "...",
            "new_password": "...",
            "confirm_password": "..."
        }

    On success: clears must_change_password flag and returns 200.
    Frontend should redirect to the dashboard after this.
    """

    permission_classes = [IsAuthenticatedTenantUser]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Password changed successfully."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Re-export simplejwt's refresh view so it lives under /api/auth/
class TokenRefreshView(TokenRefreshView):
    """
    POST /api/auth/token/refresh/

    Standard simplejwt refresh — exchange a valid refresh token
    for a new access token.
    """
    pass