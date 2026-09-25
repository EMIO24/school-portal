"""School-owned identity and readiness derived from existing operational data."""
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsSchoolAdmin
from academics.models import AcademicSession, Term
from enrollment.models import ClassLevel, ClassArm, StaffProfile, Subject, SubjectAssignment
from gradebook.scoring import policy_for, ScoringInput
from gradebook.serializers import CA_MAXIMA, MAX_EXAM
from .models import School, PlatformEvent
from .platform import PlatformSchoolLogo


class SchoolIdentitySerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = ['name', 'motto', 'address', 'phone', 'email', 'logo']
        read_only_fields = ['logo']

    def to_internal_value(self, data):
        if set(data) - (set(self.fields) - {'logo'}):
            raise serializers.ValidationError({'detail':'Only school identity and contact fields can be changed here.'})
        return super().to_internal_value(data)


class SchoolSetup(APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        school = request.tenant
        session = AcademicSession.objects.filter(school=school, is_current=True).first()
        term = Term.objects.filter(session=session, is_current=True).first() if session else None
        arms = list(ClassArm.objects.filter(school=school).values('id', 'class_level_id'))
        subjects = list(Subject.objects.filter(school=school).prefetch_related('class_levels'))
        assigned = set(SubjectAssignment.objects.filter(school=school, term=term, teacher__user__is_active=True,
            teacher__user__role='teacher', teacher__employment_status='active').values_list('class_arm_id', 'subject_id')) if term else set()
        expected = set()
        for subject in subjects:
            levels = {level.pk for level in subject.class_levels.all()}
            expected.update((arm['id'], subject.pk) for arm in arms if not levels or arm['class_level_id'] in levels)
        missing = len(expected - assigned)
        policy = policy_for(school, term) if term else None
        valid_scoring = bool(policy and ScoringInput(data={'components':policy.components,'bands':policy.bands}).is_valid())
        steps = [
            ('identity', 'School identity', bool(school.name and school.address and (school.phone or school.email)), '/admin/setup#identity'),
            ('session', 'Current academic session', bool(session), '/admin/calendar'),
            ('term', 'Current term', bool(term), '/admin/calendar'),
            ('classes', 'Classes and arms', bool(arms), '/admin/setup#classes'),
            ('subjects', 'Subjects', bool(subjects), '/admin/subjects'),
            ('teachers', 'Active teachers', StaffProfile.objects.filter(school=school, user__role='teacher', user__is_active=True, employment_status='active').exists(), '/admin/staff'),
            ('assignments', 'Teacher assignments', bool(term and expected) and not missing, '/admin/subject-assignments'),
            ('assessment', 'Assessment structure', valid_scoring, '/admin/setup#assessment'),
            ('grading', 'Grading ranges', valid_scoring, '/admin/setup#assessment'),
        ]
        return Response({'identity': SchoolIdentitySerializer(school).data, 'class_level_choices':ClassLevel.LEVEL_CHOICES,
            'steps': [{'key':key, 'label':label, 'complete':done, 'url':url} for key,label,done,url in steps],
            'missing_assignments': missing, 'session':session.name if session else None,
            'term':term.get_name_display() if term else None,
            'assessment': {c['key']:c['maximum'] for c in policy.components} if policy else {**CA_MAXIMA, 'exam_score':MAX_EXAM}})

    def patch(self, request):
        form = SchoolIdentitySerializer(request.tenant, data=request.data, partial=True)
        form.is_valid(raise_exception=True)
        form.save()
        PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email,
            action='school.identity_updated', target=str(request.tenant.pk), details={'fields':list(form.validated_data)})
        return Response(form.data)


class SchoolSetupLogo(PlatformSchoolLogo):
    permission_classes = [IsSchoolAdmin]

    def post(self, request):
        return super().post(request, request.tenant.pk)

    def delete(self, request):
        return super().delete(request, request.tenant.pk)
