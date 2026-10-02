from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSchoolAdmin
from enrollment.models import ClassArm, StaffProfile
from .models import Campus
from .security import audit


class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ["id", "name", "code", "address", "phone", "email", "is_primary", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        school = self.context["request"].tenant
        code = attrs.get("code", getattr(self.instance, "code", ""))
        qs = Campus.objects.filter(school=school, code__iexact=code)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"code": "This campus code already exists."})
        return attrs


class CampusListCreate(APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        return Response(CampusSerializer(Campus.objects.filter(school=request.tenant), many=True).data)

    def post(self, request):
        if request.tenant.subscription_plan != "enterprise":
            return Response({"detail": "Multi-campus management requires Enterprise."}, status=403)
        form = CampusSerializer(data=request.data, context={"request": request})
        form.is_valid(raise_exception=True)
        if form.validated_data.get("is_primary"):
            Campus.objects.filter(school=request.tenant, is_primary=True).update(is_primary=False)
        campus = form.save(school=request.tenant)
        audit(request, "campus.created", target=f"campus:{campus.pk}", details={"school_id": request.tenant.pk})
        return Response(CampusSerializer(campus).data, status=201)


class CampusDetail(APIView):
    permission_classes = [IsSchoolAdmin]

    def patch(self, request, pk):
        campus = Campus.objects.filter(pk=pk, school=request.tenant).first()
        if not campus:
            return Response(status=404)
        form = CampusSerializer(campus, data=request.data, partial=True, context={"request": request})
        form.is_valid(raise_exception=True)
        if form.validated_data.get("is_primary"):
            Campus.objects.filter(school=request.tenant, is_primary=True).exclude(pk=campus.pk).update(is_primary=False)
        campus = form.save()
        audit(request, "campus.updated", target=f"campus:{campus.pk}", details={"school_id": request.tenant.pk})
        return Response(CampusSerializer(campus).data)

    def delete(self, request, pk):
        campus = Campus.objects.filter(pk=pk, school=request.tenant).first()
        if not campus:
            return Response(status=404)
        if ClassArm.objects.filter(campus=campus).exists() or StaffProfile.objects.filter(campus=campus).exists():
            return Response({"detail": "Campus has institutional history. Mark it inactive instead of deleting it."}, status=409)
        campus.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
