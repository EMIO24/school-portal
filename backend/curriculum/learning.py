"""Batch 17 lesson planning and institutional academic-resource workflows."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import Term
from enrollment.models import ClassArm, ClassLevel, Subject, SubjectAssignment
from tenants.security import audit
from .models import (
    AcademicResource, AcademicStandardTopic, CurriculumTopic, LessonPlan,
)


def _base_access(request):
    school, user = getattr(request, 'tenant', None), request.user
    return bool(
        school and user.is_authenticated and user.is_active and not user.must_change_password
        and user.school_id == school.pk and user.role in ('school_admin', 'teacher')
    )


def _manager(request):
    return _base_access(request) and request.user.role == 'school_admin'


def _positive(value):
    try:
        value = int(value)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _assigned(request, term, arm, subject):
    if request.user.role == 'school_admin':
        return True
    return SubjectAssignment.objects.filter(
        school=request.tenant, teacher__user=request.user, teacher__employment_status='active',
        term=term, class_arm=arm, subject=subject,
    ).exists()


def _errors(exc):
    return exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages}


def _plan_data(plan):
    return {
        'id': plan.pk, 'term': plan.term_id, 'class_arm': plan.class_arm_id,
        'class_name': plan.class_arm.full_name, 'subject': plan.subject_id,
        'subject_name': plan.subject.name, 'curriculum_topic': plan.curriculum_topic_id,
        'curriculum_topic_title': plan.curriculum_topic.title, 'teacher': plan.teacher_id,
        'teacher_name': plan.teacher.get_full_name(), 'title': plan.title,
        'objectives': plan.objectives, 'activities': plan.activities, 'assessment': plan.assessment,
        'status': plan.status, 'revision': plan.revision, 'reviewed_by': plan.reviewed_by_id,
        'approved_by': plan.approved_by_id, 'approved_at': plan.approved_at,
        'created_at': plan.created_at, 'updated_at': plan.updated_at,
    }


def _resource_data(resource):
    return {
        'id': resource.pk, 'class_level': resource.class_level_id,
        'class_level_name': resource.class_level.name, 'subject': resource.subject_id,
        'subject_name': resource.subject.name, 'standard_topic': resource.standard_topic_id,
        'title': resource.title, 'kind': resource.kind, 'content': resource.content,
        'external_url': resource.external_url, 'status': resource.status,
        'revision': resource.revision, 'supersedes': resource.supersedes_id,
        'created_by': resource.created_by_id, 'reviewed_by': resource.reviewed_by_id,
        'approved_by': resource.approved_by_id, 'approved_at': resource.approved_at,
        'created_at': resource.created_at, 'updated_at': resource.updated_at,
    }


class LessonPlanListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _base_access(request):
            return Response({'detail': 'Teaching planning access required.'}, status=403)
        rows = LessonPlan.objects.filter(school=request.tenant).select_related(
            'term__session', 'class_arm__class_level', 'subject', 'curriculum_topic', 'teacher'
        ).order_by('-updated_at')
        if request.user.role == 'teacher':
            rows = rows.filter(teacher=request.user)
        for key, field in (('term', 'term_id'), ('class_arm', 'class_arm_id'), ('subject', 'subject_id'), ('status', 'status')):
            value = request.query_params.get(key)
            if value:
                if key != 'status' and not str(value).isdigit():
                    return Response({key: 'Choose a valid value.'}, status=400)
                rows = rows.filter(**{field: value})
        return Response({'lesson_plans': [_plan_data(row) for row in rows]})

    @transaction.atomic
    def post(self, request):
        if not _base_access(request):
            return Response({'detail': 'Teaching planning access required.'}, status=403)
        school = request.tenant
        term = Term.objects.filter(pk=_positive(request.data.get('term')), session__school=school).first()
        arm = ClassArm.objects.filter(pk=_positive(request.data.get('class_arm')), school=school).select_related('class_level').first()
        subject = Subject.objects.filter(pk=_positive(request.data.get('subject')), school=school).first()
        topic = CurriculumTopic.objects.filter(
            pk=_positive(request.data.get('curriculum_topic')), week__plan__school=school
        ).select_related('week__plan').first()
        if not all((term, arm, subject, topic)):
            return Response({'detail': 'Choose a valid term, class, subject and curriculum topic.'}, status=400)
        if not _assigned(request, term, arm, subject):
            return Response({'detail': 'This class/subject is not assigned to you.'}, status=403)
        teacher = request.user if request.user.role == 'teacher' else None
        if request.user.role == 'school_admin':
            teacher_id = _positive(request.data.get('teacher'))
            from accounts.models import CustomUser
            teacher = CustomUser.objects.filter(pk=teacher_id, school=school, role='teacher', is_active=True).first()
            if not teacher or not _assigned(type('R', (), {'user': teacher, 'tenant': school})(), term, arm, subject):
                return Response({'teacher': 'Choose the assigned active teacher.'}, status=400)
        title = request.data.get('title', '')
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 180:
            return Response({'title': 'Provide a lesson-plan title.'}, status=400)
        plan = LessonPlan(
            school=school, term=term, class_arm=arm, subject=subject, curriculum_topic=topic,
            teacher=teacher, title=title.strip(), objectives=str(request.data.get('objectives', '')).strip(),
            activities=str(request.data.get('activities', '')).strip(),
            assessment=str(request.data.get('assessment', '')).strip(),
        )
        try:
            plan.full_clean()
            plan.save()
        except ValidationError as exc:
            return Response(_errors(exc), status=400)
        except IntegrityError:
            return Response({'detail': 'A lesson-plan revision already exists for this topic.'}, status=409)
        audit(request, 'curriculum.lesson_plan_created', target=f'lesson-plan:{plan.pk}',
              details={'school_id': school.pk, 'teacher_id': teacher.pk, 'topic_id': topic.pk})
        return Response({'lesson_plan': _plan_data(plan)}, status=201)


class LessonPlanTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, plan_id):
        if not _base_access(request):
            return Response({'detail': 'Teaching planning access required.'}, status=403)
        plan = LessonPlan.objects.select_for_update().filter(pk=plan_id, school=request.tenant).select_related(
            'term', 'class_arm__class_level', 'subject', 'curriculum_topic', 'teacher'
        ).first()
        if not plan:
            return Response({'detail': 'Lesson plan not found.'}, status=404)
        action = request.data.get('action')
        if plan.status == LessonPlan.Status.DRAFT:
            if action != 'submit' or (request.user.role == 'teacher' and plan.teacher_id != request.user.pk):
                return Response({'detail': 'Only the owning teacher can submit this draft.'}, status=409)
            plan.status = LessonPlan.Status.SUBMITTED
        elif plan.status == LessonPlan.Status.SUBMITTED:
            if action != 'review' or not _manager(request):
                return Response({'detail': 'School management review required.'}, status=409)
            plan.status = LessonPlan.Status.REVIEWED
            plan.reviewed_by = request.user
        elif plan.status == LessonPlan.Status.REVIEWED:
            if action != 'approve' or not _manager(request):
                return Response({'detail': 'School management approval required.'}, status=409)
            plan.status = LessonPlan.Status.APPROVED
            plan.approved_by = request.user
            plan.approved_at = timezone.now()
        else:
            return Response({'detail': 'Approved lesson plans are preserved as historical review evidence.'}, status=409)
        plan.save()
        audit(request, 'curriculum.lesson_plan_' + plan.status, target=f'lesson-plan:{plan.pk}',
              details={'school_id': request.tenant.pk, 'revision': plan.revision})
        return Response({'lesson_plan': _plan_data(plan)})


class AcademicResourceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _base_access(request):
            return Response({'detail': 'Academic resource access required.'}, status=403)
        rows = AcademicResource.objects.filter(school=request.tenant).select_related(
            'class_level', 'subject', 'standard_topic__standard'
        ).order_by('-updated_at')
        if request.user.role == 'teacher':
            scopes = set(SubjectAssignment.objects.filter(
                school=request.tenant, teacher__user=request.user, teacher__employment_status='active'
            ).values_list('class_arm__class_level_id', 'subject_id'))
            rows = [row for row in rows if (row.class_level_id, row.subject_id) in scopes and
                    (row.created_by_id == request.user.pk or row.status == AcademicResource.Status.APPROVED)]
        return Response({'resources': [_resource_data(row) for row in rows]})

    @transaction.atomic
    def post(self, request):
        if not _base_access(request):
            return Response({'detail': 'Academic resource access required.'}, status=403)
        school = request.tenant
        level = ClassLevel.objects.filter(pk=_positive(request.data.get('class_level')), school=school).first()
        subject = Subject.objects.filter(pk=_positive(request.data.get('subject')), school=school).first()
        standard_topic = None
        if request.data.get('standard_topic') not in (None, ''):
            standard_topic = AcademicStandardTopic.objects.filter(
                pk=_positive(request.data.get('standard_topic')), standard__school=school
            ).select_related('standard').first()
        if not level or not subject:
            return Response({'detail': 'Choose a class level and subject in this school.'}, status=400)
        if request.user.role == 'teacher' and not SubjectAssignment.objects.filter(
            school=school, teacher__user=request.user, teacher__employment_status='active',
            class_arm__class_level=level, subject=subject
        ).exists():
            return Response({'detail': 'This class/subject is not assigned to you.'}, status=403)
        title = request.data.get('title', '')
        kind = request.data.get('kind')
        if not isinstance(title, str) or not title.strip() or kind not in AcademicResource.Kind.values:
            return Response({'detail': 'Provide a title and valid resource type.'}, status=400)
        resource = AcademicResource(
            school=school, class_level=level, subject=subject, standard_topic=standard_topic,
            title=title.strip(), kind=kind, content=str(request.data.get('content', '')).strip(),
            external_url=str(request.data.get('external_url', '')).strip(), created_by=request.user,
        )
        try:
            resource.full_clean()
            resource.save()
        except ValidationError as exc:
            return Response(_errors(exc), status=400)
        except IntegrityError:
            return Response({'detail': 'This resource revision already exists.'}, status=409)
        audit(request, 'curriculum.resource_created', target=f'academic-resource:{resource.pk}',
              details={'school_id': school.pk})
        return Response({'resource': _resource_data(resource)}, status=201)


class AcademicResourceTransitionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, resource_id):
        if not _base_access(request):
            return Response({'detail': 'Academic resource access required.'}, status=403)
        resource = AcademicResource.objects.select_for_update().filter(
            pk=resource_id, school=request.tenant
        ).select_related('class_level', 'subject').first()
        if not resource:
            return Response({'detail': 'Academic resource not found.'}, status=404)
        action = request.data.get('action')
        if resource.status == AcademicResource.Status.DRAFT:
            if action != 'submit' or (request.user.role == 'teacher' and resource.created_by_id != request.user.pk):
                return Response({'detail': 'Only the author can submit this draft.'}, status=409)
            resource.status = AcademicResource.Status.SUBMITTED
        elif resource.status == AcademicResource.Status.SUBMITTED:
            if action != 'review' or not _manager(request):
                return Response({'detail': 'School management review required.'}, status=409)
            resource.status = AcademicResource.Status.REVIEWED
            resource.reviewed_by = request.user
        elif resource.status == AcademicResource.Status.REVIEWED:
            if action != 'approve' or not _manager(request):
                return Response({'detail': 'School management approval required.'}, status=409)
            resource.status = AcademicResource.Status.APPROVED
            resource.approved_by = request.user
            resource.approved_at = timezone.now()
        else:
            return Response({'detail': 'Approved resources are immutable; create a new revision.'}, status=409)
        resource.save()
        audit(request, 'curriculum.resource_' + resource.status, target=f'academic-resource:{resource.pk}',
              details={'school_id': request.tenant.pk, 'revision': resource.revision})
        return Response({'resource': _resource_data(resource)})


class AcademicResourceReviseView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, resource_id):
        if not _base_access(request):
            return Response({'detail': 'Academic resource access required.'}, status=403)
        previous = AcademicResource.objects.select_for_update().filter(
            pk=resource_id, school=request.tenant, status=AcademicResource.Status.APPROVED
        ).select_related('class_level', 'subject').first()
        if not previous:
            return Response({'detail': 'Only an approved resource can start a new revision.'}, status=409)
        if request.user.role == 'teacher' and not SubjectAssignment.objects.filter(
            school=request.tenant, teacher__user=request.user, teacher__employment_status='active',
            class_arm__class_level=previous.class_level, subject=previous.subject
        ).exists():
            return Response({'detail': 'This class/subject is not assigned to you.'}, status=403)
        if AcademicResource.objects.filter(supersedes=previous).exists():
            return Response({'detail': 'A newer revision already exists.'}, status=409)
        latest = AcademicResource.objects.filter(
            school=request.tenant, class_level=previous.class_level, subject=previous.subject,
            title=previous.title
        ).order_by('-revision').values_list('revision', flat=True).first() or previous.revision
        revised = AcademicResource.objects.create(
            school=request.tenant, class_level=previous.class_level, subject=previous.subject,
            standard_topic=previous.standard_topic, title=previous.title, kind=previous.kind,
            content=previous.content, external_url=previous.external_url, revision=latest + 1,
            supersedes=previous, created_by=request.user,
        )
        audit(request, 'curriculum.resource_revised', target=f'academic-resource:{revised.pk}',
              details={'school_id': request.tenant.pk, 'supersedes': previous.pk})
        return Response({'resource': _resource_data(revised)}, status=201)
