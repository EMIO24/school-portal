from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db import transaction
from django.db.models.deletion import ProtectedError

from accounts.permissions import IsSchoolAdmin
from enrollment.models import ClassArm, StaffProfile, StudentProfile
from .models import Campus, School
from .security import audit


class CampusSerializer(serializers.ModelSerializer):
    class_count = serializers.SerializerMethodField()
    staff_count = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    class Meta:
        model = Campus
        fields = ["id", "name", "code", "address", "phone", "email", "is_primary", "is_active", "class_count", "staff_count", "student_count", "created_at"]
        read_only_fields = ["id", "class_count", "staff_count", "student_count", "created_at"]

    def get_class_count(self, obj):
        return obj.class_arms_by_campus.count()

    def get_staff_count(self, obj):
        return obj.staff_members.filter(employment_status="active").count()

    def get_student_count(self, obj):
        return StudentProfile.objects.filter(
            school=obj.school, status="active", current_class__campus=obj
        ).count()

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

    @transaction.atomic
    def post(self, request):
        School.objects.select_for_update().get(pk=request.tenant.pk)
        if request.tenant.subscription_plan != "enterprise":
            return Response({"detail": "Multi-campus management requires Enterprise."}, status=403)
        form = CampusSerializer(data=request.data, context={"request": request})
        form.is_valid(raise_exception=True)
        if form.validated_data.get("is_primary"):
            Campus.objects.filter(school=request.tenant, is_primary=True).update(is_primary=False)
        campus = form.save(school=request.tenant)
        if not request.tenant.uses_class_arms:
            from enrollment.class_structure import ensure_default_arm
            from enrollment.models import ClassLevel
            for level in ClassLevel.objects.filter(school=request.tenant):
                ensure_default_arm(school=request.tenant, class_level=level, campus=campus)
        audit(request, "campus.created", target=f"campus:{campus.pk}", details={"school_id": request.tenant.pk})
        return Response(CampusSerializer(campus).data, status=201)


class CampusDetail(APIView):
    permission_classes = [IsSchoolAdmin]

    @transaction.atomic
    def patch(self, request, pk):
        School.objects.select_for_update().get(pk=request.tenant.pk)
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

    @transaction.atomic
    def delete(self, request, pk):
        School.objects.select_for_update().get(pk=request.tenant.pk)
        campus = Campus.objects.filter(pk=pk, school=request.tenant).first()
        if not campus:
            return Response(status=404)
        if ClassArm.objects.filter(campus=campus).exists() or StaffProfile.objects.filter(campus=campus).exists():
            return Response({"detail": "Campus has institutional history. Mark it inactive instead of deleting it."}, status=409)
        try:
            campus.delete()
        except ProtectedError:
            return Response({"detail": "Campus has institutional history. Mark it inactive instead of deleting it."}, status=409)
        return Response(status=status.HTTP_204_NO_CONTENT)
