"""
enrollment/assignment_views.py

SubjectAssignmentViewSet:
  GET    /api/subject-assignments/           — list (filterable by term, class_arm, teacher)
  POST   /api/subject-assignments/           — create single assignment
  DELETE /api/subject-assignments/{id}/      — remove assignment
  GET    /api/subject-assignments/grid/      — ?term=<id> full grid (arms × subjects)
  GET    /api/subjects/by-class/{arm_id}/    — subjects offered to a class arm

StaffViewSet (extended via mixin):
  POST   /api/staff/{id}/assign-subjects/    — bulk set assignments for a teacher+term

SubjectViewSet (extended with by-class action):
  GET    /api/subjects/by-class/{arm_id}/
"""

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsSchoolAdmin, IsAuthenticatedTenantUser, IsSchoolAdminOrTeacher
from tenants.mixins import TenantMixin

from .models import ClassArm, StaffProfile, Subject, SubjectAssignment
from .assignment_serializers import (
    AssignmentGridSerializer,
    BulkAssignSerializer,
    SubjectAssignmentSerializer,
)


class SubjectAssignmentViewSet(TenantMixin, viewsets.ModelViewSet):
    """
    CRUD for SubjectAssignment.

    Key filters (query params):
      ?term=<id>       — all assignments for a term
      ?class_arm=<id>  — all assignments in a class arm
      ?teacher=<id>    — all assignments for a teacher (StaffProfile id)
      ?subject=<id>    — all assignments for a subject
    """

    serializer_class = SubjectAssignmentSerializer
    queryset         = SubjectAssignment.objects.select_related(
        "teacher__user", "subject", "class_arm__class_level",
        "session", "term",
    )
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "grid"):
            return [IsAuthenticatedTenantUser()]
        return [IsSchoolAdmin()]

    def get_queryset(self):
        tenant = self._get_tenant()
        qs     = SubjectAssignment.objects.select_related(
            "teacher__user", "subject", "class_arm__class_level",
            "session", "term",
        ).filter(school=tenant)

        for param in ("term", "class_arm", "teacher", "subject", "session"):
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{f"{param}_id": val})

        return qs.order_by("class_arm__class_level__order_index",
                           "class_arm__name", "subject__name")

    def perform_create(self, serializer):
        tenant = self._get_tenant()
        # Validate foreign keys belong to tenant
        teacher   = serializer.validated_data["teacher"]
        subject   = serializer.validated_data["subject"]
        class_arm = serializer.validated_data["class_arm"]

        if teacher.school != tenant:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Teacher does not belong to this school.")
        if subject.school != tenant:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Subject does not belong to this school.")
        if class_arm.school != tenant:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Class arm does not belong to this school.")

        serializer.save(school=tenant)

    # ── Grid view ─────────────────────────────────────────────────────────

    @action(detail=False, methods=["get"], url_path="grid")
    def grid(self, request):
        """
        GET /api/subject-assignments/grid/?term=<id>

        Returns the full assignment matrix for a term:
          rows = class arms, columns = subjects
          cells = { teacher_name, teacher_id, staff_id } | null
        """
        tenant  = self._get_tenant()
        term_id = request.query_params.get("term")

        if not term_id:
            return Response(
                {"error": "?term=<id> is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch all assignments for this term
        assignments = list(
            SubjectAssignment.objects.filter(
                school=tenant, term_id=term_id
            ).select_related(
                "teacher__user", "subject", "class_arm__class_level"
            )
        )

        # All class arms for this school
        arms = list(
            ClassArm.objects.filter(school=tenant)
            .select_related("class_level")
            .order_by("class_level__order_index", "name")
        )

        # All subjects for this school
        subjects = list(
            Subject.objects.filter(school=tenant).order_by("name")
        )

        serializer = AssignmentGridSerializer(
            instance={},
            assignments=assignments,
            arms=arms,
            subjects=subjects,
        )
        return Response(serializer.to_representation({}))


# ── Mixin for StaffViewSet's assign-subjects action ───────────────────────

class AssignSubjectsMixin:
    """
    Mixin to be added to StaffViewSet.
    Adds POST {id}/assign-subjects/ endpoint.
    """

    @action(detail=True, methods=["post"], url_path="assign-subjects")
    def assign_subjects(self, request, pk=None):
        """
        POST /api/staff/{id}/assign-subjects/

        Replaces all subject assignments for this teacher in the given term.

        Body:
        {
            "session_id":  1,
            "term_id":     2,
            "assignments": [
                { "subject_id": 3, "class_arm_id": 5 },
                { "subject_id": 4, "class_arm_id": 5 }
            ]
        }
        """
        teacher = self.get_object()
        tenant  = self._get_tenant()

        serializer = BulkAssignSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        session_id  = serializer.validated_data["session_id"]
        term_id     = serializer.validated_data["term_id"]
        assignments = serializer.validated_data["assignments"]

        # Validate session + term belong to tenant
        from academics.models import AcademicSession, Term
        try:
            session = AcademicSession.objects.get(pk=session_id, school=tenant)
            term    = Term.objects.get(pk=term_id, session=session)
        except (AcademicSession.DoesNotExist, Term.DoesNotExist):
            return Response(
                {"error": "Session or term not found for this school."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        errors  = []
        created = []

        with transaction.atomic():
            # Remove all existing assignments for this teacher + term
            SubjectAssignment.objects.filter(
                school=tenant, teacher=teacher, term=term
            ).delete()

            for item in assignments:
                try:
                    subject   = Subject.objects.get(pk=item["subject_id"],   school=tenant)
                    class_arm = ClassArm.objects.get(pk=item["class_arm_id"], school=tenant)
                except (Subject.DoesNotExist, ClassArm.DoesNotExist):
                    errors.append({
                        "subject_id":   item.get("subject_id"),
                        "class_arm_id": item.get("class_arm_id"),
                        "error": "Subject or class arm not found.",
                    })
                    continue

                try:
                    assignment, _ = SubjectAssignment.objects.get_or_create(
                        school=tenant, teacher=teacher,
                        subject=subject, class_arm=class_arm,
                        session=session, term=term,
                    )
                    created.append(assignment)
                except Exception as e:
                    errors.append({
                        "subject_id":   item["subject_id"],
                        "class_arm_id": item["class_arm_id"],
                        "error": str(e),
                    })

        return Response({
            "created":       len(created),
            "errors":        errors,
            "assignments":   SubjectAssignmentSerializer(created, many=True).data,
        }, status=status.HTTP_200_OK)


# ── Subject by-class action ────────────────────────────────────────────────

class SubjectByClassMixin:
    """
    Mixin for SubjectViewSet — adds GET subjects/by-class/{arm_id}/
    """

    @action(detail=False, methods=["get"], url_path=r"by-class/(?P<arm_id>\d+)")
    def by_class(self, request, arm_id=None):
        """
        GET /api/subjects/by-class/{arm_id}/

        Returns subjects offered to the class level of this arm.
        """
        tenant = self._get_tenant()

        try:
            arm = ClassArm.objects.select_related("class_level").get(
                pk=arm_id, school=tenant
            )
        except ClassArm.DoesNotExist:
            return Response(
                {"error": "Class arm not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Subjects that include this arm's level, OR have no level restriction
        subjects = Subject.objects.filter(school=tenant).filter(
            models_Q_for_arm(arm)
        ).order_by("name")

        from .serializers import SubjectSerializer
        return Response(SubjectSerializer(subjects, many=True).data)


def models_Q_for_arm(arm):
    """Return a Q object: subjects offered to this arm's level, or all-levels subjects."""
    from django.db.models import Q
    return Q(class_levels=arm.class_level) | Q(class_levels__isnull=True)