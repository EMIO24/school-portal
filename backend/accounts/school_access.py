"""Explicit access policies for school modules; never trust a selected tenant alone."""
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.exceptions import PermissionDenied

def owns_student(request, student_id, profile=False):
    from enrollment.models import StudentProfile
    from accounts.models import ParentStudentLink
    qs = StudentProfile.objects.filter(school=request.tenant)
    qs = qs.filter(pk=student_id) if profile else qs.filter(user_id=student_id)
    student = qs.first()
    if not student:
        return False
    if request.user.role == 'student':
        return student.user_id == request.user.pk
    return request.user.role == 'parent' and ParentStudentLink.objects.filter(school=request.tenant, parent=request.user, student=student).exists()

def require_assignment(request, class_arm, term=None, subject=None):
    if request.user.role != 'teacher':
        return
    from enrollment.models import SubjectAssignment
    qs = SubjectAssignment.objects.filter(school=request.tenant, teacher__user=request.user, teacher__employment_status='active', class_arm_id=class_arm)
    if term: qs = qs.filter(term_id=term)
    if subject: qs = qs.filter(subject_id=subject)
    if not qs.exists():
        raise PermissionDenied('This class/subject is not assigned to you.')

class SchoolModulePermission(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        tenant = getattr(request, 'tenant', None)
        if not user or not user.is_authenticated or not user.is_active or tenant is None or user.school_id != tenant.pk:
            return False
        if user.must_change_password:
            return False
        role, module, name = user.role, view.__module__.split('.')[0], type(view).__name__
        action = getattr(view, 'action', '')
        if role == 'school_admin':
            return True
        if module in ('notifications', 'promotion'):
            return False
        if module == 'timetable':
            return request.method in SAFE_METHODS
        if module == 'cbt':
            if role == 'teacher': return True
            return role == 'student' and name == 'CBTExamViewSet' and action in ('available','start','save_answer','status','submit','log_tab_switch','review')
        if module == 'gradebook':
            return role == 'teacher' and action not in ('publish','destroy')
        if module == 'attendance':
            if role == 'teacher': return action != 'destroy'
            if request.method not in SAFE_METHODS: return False
            sid = view.kwargs.get('student_id') or request.query_params.get('student')
            return action in ('report','student_report') and bool(sid) and owns_student(request, sid)
        if module == 'results':
            if role == 'teacher':
                from enrollment.models import StudentProfile
                profile = StudentProfile.objects.filter(school=tenant, user_id=view.kwargs.get('student_id')).first()
                if not profile: return False
                require_assignment(request, profile.current_class_id, request.query_params.get('term'))
                return name in ('SlipDataView','ResultSlipPDFView','ResultRemarkView') and request.method in SAFE_METHODS
            return request.method in SAFE_METHODS and name in ('SlipDataView','ResultSlipPDFView','ResultRemarkView') and owns_student(request, view.kwargs.get('student_id'))
        if module == 'analytics':
            return request.method in SAFE_METHODS and name in ('StudentTrendsView','TranscriptPDFView') and owns_student(request, view.kwargs.get('pk'), profile=True)
        return False


def assigned_classes(request):
    from enrollment.models import SubjectAssignment
    return SubjectAssignment.objects.filter(school=request.tenant, teacher__user=request.user).values_list('class_arm_id', flat=True)

class TenantRelationsMixin:
    def validate(self, attrs):
        from rest_framework import serializers
        attrs = super().validate(attrs)
        request = self.context.get('request')
        if request is None:
            raise serializers.ValidationError('School context is required.')
        for name, value in attrs.items():
            values = value if isinstance(value, list) else [value]
            for obj in values:
                if not hasattr(obj, '_meta'): continue
                school_id = getattr(obj, 'school_id', None)
                if school_id is None and hasattr(obj, 'session'): school_id = obj.session.school_id
                if school_id is not None and school_id != request.tenant.pk:
                    raise serializers.ValidationError({name:'Select a record belonging to this school.'})
        arm = attrs.get('class_arm', getattr(self.instance, 'class_arm', None))
        term = attrs.get('term', getattr(self.instance, 'term', None))
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        session = attrs.get('session', getattr(self.instance, 'session', None))
        if term and session and term.session_id != session.pk:
            raise serializers.ValidationError({'term':'Term must belong to the selected session.'})
        if arm:
            require_assignment(request, arm.pk, getattr(term,'pk',None), getattr(subject,'pk',None))
            student = attrs.get('student', getattr(self.instance, 'student', None))
            if student is not None and hasattr(student, 'role'):
                from enrollment.models import StudentProfile
                if student.role != 'student' or not StudentProfile.objects.filter(user=student, school=request.tenant, current_class=arm).exists():
                    raise serializers.ValidationError({'student':'Select a student enrolled in this class.'})
        return attrs
