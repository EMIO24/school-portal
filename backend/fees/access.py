from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from enrollment.models import StudentProfile

def check_student_access(user, student):
    if user.school_id != student.school_id:
        raise PermissionDenied('This student belongs to another school.')
    if user.role == 'school_admin' or (user.role == 'student' and student.user_id == user.pk):
        return
    if user.role == 'parent' and student.parent_links.filter(parent=user, school_id=student.school_id).exists():
        return
    raise PermissionDenied('You cannot access payments for this student.')

def payment_student(request, pk):
    student = get_object_or_404(StudentProfile.objects.select_related('user', 'current_class__class_level'), pk=pk, school=request.tenant)
    check_student_access(request.user, student)
    return student
