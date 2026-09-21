"""
tenants/views.py

Views for School onboarding (SuperAdmin) and tenant self-inspection.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import AcademicSession, Term
from accounts.permissions import IsAuthenticatedTenantUser, IsSuperAdmin
from enrollment.models import ClassArm, ClassLevel, StaffProfile, StudentProfile, Subject, SubjectAssignment
from gradebook.models import GradeScale
from .models import School
from .serializers import SchoolPublicSerializer, SchoolSerializer



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


class SchoolSetupStatusView(APIView):
    """Return the progress of the school setup / academic onboarding wizard."""

    permission_classes = [IsAuthenticatedTenantUser]

    def get(self, request):
        school = request.tenant
        sessions = AcademicSession.objects.filter(school=school)
        terms = Term.objects.filter(session__school=school)
        class_levels = ClassLevel.objects.filter(school=school)
        class_arms = ClassArm.objects.filter(school=school)
        subjects = Subject.objects.filter(school=school)
        teachers = StaffProfile.objects.filter(school=school, user__role='teacher')
        assignments = SubjectAssignment.objects.filter(school=school)
        grade_scales = GradeScale.objects.filter(school=school)

        current_session = sessions.order_by('-start_date').first()
        current_term = terms.order_by('-session__start_date', 'name').first()
        counts = {
            'class_levels': class_levels.count(),
            'class_arms': class_arms.count(),
            'subjects': subjects.count(),
            'teachers': teachers.count(),
            'students': StudentProfile.objects.filter(school=school).count(),
            'assignments': assignments.count(),
            'grade_scales': grade_scales.count(),
        }

        assessment_ready = any(
            subject.max_ca_score + subject.max_exam_score == 100 for subject in subjects.all()
        )

        checklist = {
            'session_created': current_session is not None,
            'term_created': current_term is not None,
            'class_levels_created': counts['class_levels'] > 0 or counts['class_arms'] > 0,
            'subjects_created': counts['subjects'] > 0,
            'teachers_created': counts['teachers'] > 0,
            'teacher_assignments_created': counts['assignments'] > 0,
            'assessment_structure_ready': assessment_ready,
            'grading_system_ready': counts['grade_scales'] >= 9,
            'students_enrolled': counts['students'] > 0,
        }

        steps = [
            {
                'key': 'academic_session',
                'title': 'Academic Session',
                'description': 'Set the school year and current session.',
                'done': checklist['session_created'],
                'link': '/admin/calendar',
            },
            {
                'key': 'terms',
                'title': 'Terms',
                'description': 'Add the terms scheduled for the active session.',
                'done': checklist['term_created'],
                'link': '/admin/calendar',
            },
            {
                'key': 'classes_and_arms',
                'title': 'Classes & Arms',
                'description': 'Create the class structure and class arms.',
                'done': checklist['class_levels_created'],
                'link': '/admin/students',
            },
            {
                'key': 'subjects',
                'title': 'Subjects',
                'description': 'Configure the subjects taught across the school.',
                'done': checklist['subjects_created'],
                'link': '/admin/subjects',
            },
            {
                'key': 'teachers',
                'title': 'Teachers',
                'description': 'Create teacher accounts and profiles.',
                'done': checklist['teachers_created'],
                'link': '/admin/staff',
            },
            {
                'key': 'teacher_assignments',
                'title': 'Teacher Assignments',
                'description': 'Assign teachers to subjects and classes.',
                'done': checklist['teacher_assignments_created'],
                'link': '/admin/subject-assignments',
            },
            {
                'key': 'assessment_structure',
                'title': 'Assessment Structure',
                'description': 'Set the CA and exam weighting for academic subjects.',
                'done': checklist['assessment_structure_ready'],
                'link': '/admin/subjects',
            },
            {
                'key': 'grading_system',
                'title': 'Grading System',
                'description': 'Confirm the school grade scale is active and ready.',
                'done': checklist['grading_system_ready'],
                'link': '/admin/results',
            },
        ]

        completed_steps = sum(1 for step in steps if step['done'])
        readiness = round((completed_steps / len(steps)) * 100)
        wizard_ready = all(checklist[k] for k in ['session_created', 'term_created', 'class_levels_created', 'subjects_created', 'grading_system_ready'])

        return Response({
            'school': school.slug,
            'plan': school.subscription_plan,
            'readiness': readiness,
            'wizard_ready': wizard_ready,
            'basic_setup_ready': all(checklist[k] for k in ['session_created', 'term_created', 'class_levels_created', 'subjects_created']),
            'current_session': current_session.id if current_session else None,
            'current_term': current_term.id if current_term else None,
            'counts': counts,
            'checklist': checklist,
            'steps': steps,
            'required_steps': [
                'Academic Session',
                'Terms',
                'Classes & Arms',
                'Subjects',
                'Teachers',
                'Teacher Assignments',
                'Assessment Structure',
                'Grading System',
            ],
        })