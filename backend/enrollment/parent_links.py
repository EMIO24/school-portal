from django.db import transaction
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from accounts.models import CustomUser, ParentStudentLink
from accounts.parent_auth import phone_value
from accounts.permissions import IsSchoolAdmin
from tenants.models import School, PlatformEvent
from .models import StudentProfile


class ParentLinkInput(serializers.Serializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=30)
    relationship = serializers.ChoiceField(choices=ParentStudentLink.RELATIONSHIP_CHOICES)

    def validate_phone(self, value):
        phone = phone_value(value)
        if not phone:
            raise serializers.ValidationError('Enter the parent login phone number, using 10 to 15 digits.')
        return phone


class StudentParents(APIView):
    permission_classes = [IsSchoolAdmin]

    def student(self, request, pk):
        return get_object_or_404(StudentProfile, pk=pk, school=request.tenant)

    def get(self, request, pk):
        student = self.student(request, pk)
        links = ParentStudentLink.objects.filter(student=student, school=request.tenant, parent__school=request.tenant).select_related('parent')
        return Response([{'id':link.pk, 'name':link.parent.full_name, 'email':link.parent.email,
            'phone':link.parent.phone_number, 'relationship':link.relationship} for link in links])

    @transaction.atomic
    def post(self, request, pk):
        school = School.objects.select_for_update().get(pk=request.tenant.pk)
        student = self.student(request, pk)
        form = ParentLinkInput(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data
        email = data['email'].lower()
        parent = CustomUser.objects.filter(email__iexact=email).first()
        if parent and (parent.school_id != school.pk or parent.role != 'parent' or parent.phone_number != data['phone'] or not parent.is_active):
            raise serializers.ValidationError('An account cannot be linked with these details. Check the registered parent details.')
        if not parent:
            if CustomUser.objects.filter(school=school, role='parent', phone_number=data['phone']).exists():
                raise serializers.ValidationError('This phone already belongs to a parent account. Use its registered email.')
            parent = CustomUser.objects.create_user(email=email, password=None, first_name=data['first_name'],
                last_name=data['last_name'], role='parent', school=school, phone_number=data['phone'], must_change_password=False)
        link, created = ParentStudentLink.objects.get_or_create(parent=parent, student=student,
            defaults={'school':school, 'relationship':data['relationship']})
        PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email, action='school.parent_linked',
            target=str(student.pk), details={'school_id':school.pk, 'parent_id':parent.pk, 'link_id':link.pk})
        return Response({'id':link.pk}, status=201 if created else 200)

    def delete(self, request, pk):
        student = self.student(request, pk)
        link_id = serializers.IntegerField(min_value=1).run_validation(request.query_params.get('link'))
        link = get_object_or_404(ParentStudentLink, pk=link_id, student=student, school=request.tenant)
        parent_id = link.parent_id
        link.delete()
        PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email, action='school.parent_unlinked',
            target=str(student.pk), details={'school_id':request.tenant.pk, 'parent_id':parent_id})
        return Response(status=204)
