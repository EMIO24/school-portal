"""
tenants/views.py

Views for School onboarding (SuperAdmin) and tenant self-inspection.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import School
from .serializers import SchoolPublicSerializer, SchoolSerializer


class IsSuperAdmin(IsAuthenticated):
    """
    Permission class: user must be authenticated AND have role=superadmin.

    Adjust the role-check once your User model / JWT claims are in place.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        # Support both a `role` field and a `is_superadmin` bool flag.
        return getattr(user, "role", None) == "superadmin" or getattr(
            user, "is_superadmin", False
        )


class SchoolOnboardingView(APIView):
    """
    POST /api/schools/

    Create a new School (tenant) on the platform.
    Accessible by SuperAdmin only.

    Request body: all School fields (see SchoolSerializer).
    Returns: 201 with created school data.
    """

    permission_classes = [IsSuperAdmin]

    def post(self, request):
        serializer = SchoolSerializer(data=request.data)
        if serializer.is_valid():
            school = serializer.save()
            return Response(
                SchoolSerializer(school).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        """
        GET /api/schools/

        List all schools. SuperAdmin only.
        Supports optional ?is_active= and ?plan= query params.
        """
        qs = School.objects.all()

        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        plan = request.query_params.get("plan")
        if plan:
            qs = qs.filter(subscription_plan=plan)

        serializer = SchoolSerializer(qs, many=True)
        return Response(serializer.data)


class SchoolMeView(APIView):
    """
    GET /api/school/me/

    Returns the current tenant's School info.
    Used by the frontend to load branding/theme on app start.

    No auth required — branding must be visible on the login page.
    (Sensitive fields are excluded via SchoolPublicSerializer.)
    """

    permission_classes = []  # public endpoint

    def get(self, request):
        tenant = getattr(request, "tenant", None)
        if tenant is None:
            return Response(
                {"error": "No school tenant found for this subdomain."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SchoolPublicSerializer(tenant)
        return Response(serializer.data)


class SchoolDetailView(APIView):
    """
    GET  /api/schools/<pk>/   — retrieve a school (SuperAdmin)
    PUT  /api/schools/<pk>/   — update a school (SuperAdmin)
    """

    permission_classes = [IsSuperAdmin]

    def _get_school(self, pk):
        try:
            return School.objects.get(pk=pk)
        except School.DoesNotExist:
            return None

    def get(self, request, pk):
        school = self._get_school(pk)
        if not school:
            return Response({"error": "School not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(SchoolSerializer(school).data)

    def put(self, request, pk):
        school = self._get_school(pk)
        if not school:
            return Response({"error": "School not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = SchoolSerializer(school, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)