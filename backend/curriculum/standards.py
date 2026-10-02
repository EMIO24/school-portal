"""Batch 17 academic standards, provenance, approval and continuity workflows."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academics.models import AcademicSession, Term
from enrollment.models import ClassLevel, Subject, SubjectAssignment
from tenants.security import audit
from .models import (
    AcademicStandardObjective,
    AcademicStandardTopic,
    CurriculumApplicability,
    CurriculumPlan,
    CurriculumSource,
    CurriculumTopic,
    CurriculumVersion,
    CurriculumWeek,
    LearningObjective,
    SchoolAcademicStandard,
)


def _school_user(request):
    user, school = request.user, getattr(request, 'tenant', None)
    return bool(
        school and user.is_authenticated and user.is_active and not user.must_change_password
        and user.school_id == school.pk
    )


def _manager(request):
    return _school_user(request) and request.user.role in ('school_admin', 'principal')


def _positive(value):
    try:
        value = int(value)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def _validation(error):
    if hasattr(error, 'message_dict'):
        return error.message_dict
    return {'detail': error.messages}


def _source_data(source):
    return {
        'id': source.pk,
        'name': source.name,
        'kind': source.kind,
        'jurisdiction': source.jurisdiction,
        'authority': source.authority,
        'source_url': source.source_url,
        'notes': source.notes,
        'versions': [
            {
                'id': version.pk,
                'label': version.label,
                'effective_from': version.effective_from,
                'effective_to': version.effective_to,
                'reference': version.reference,
                'notes': version.notes,
            }
            for version in source.versions.all().order_by('-effective_from', '-id')
        ],
    }


def _standard_data(standard, include_topics=True):
    data = {
        'id': standard.pk,
        'title': standard.title,
        'class_level': standard.class_level_id,
        'class_level_name': standard.class_level.name,
        'subject': standard.subject_id,
        'subject_name': standard.subject.name,
        'curriculum_version': standard.curriculum_version_id,
        'curriculum_source': standard.curriculum_version.source.name,
        'curriculum_version_label': standard.curriculum_version.label,
        'revision': standard.revision,
        'status': standard.status,
        'supersedes': standard.supersedes_id,
        'approved_by': standard.approved_by_id,
        'approved_at': standard.approved_at,
        'created_at': standard.created_at,
        'updated_at': standard.updated_at,
    }
    if include_topics:
        topics = standard.topics.prefetch_related('objectives').all()
        data['topics'] = [{
            'id': topic.pk,
            'term': topic.term,
            'title': topic.title,
            'description': topic.description,
            'position': topic.position,
            'recommended_week': topic.recommended_week,
            'requirement': topic.requirement,
            'source_reference': topic.source_reference,
            'objectives': [
                {'id': objective.pk, 'text': objective.text, 'position': objective.position}
                for objective in topic.objectives.all()
            ],
        } for topic in topics]
    return data


def _teacher_can_read_standard(request, standard):
    if request.user.role in ('school_admin', 'principal'):
        return True
    if request.user.role not in ('teacher', 'class_teacher') or standard.status != SchoolAcademicStandard.Status.APPROVED:
        return False
    return SubjectAssignment.objects.filter(
        school=request.tenant,
        teacher__user=request.user,
        teacher__employment_status='active',
        class_arm__class_level=standard.class_level,
        subject=standard.subject,
    ).exists()


class CurriculumSourceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _school_user(request) or request.user.role not in ('school_admin', 'principal', 'teacher', 'class_teacher'):
            return Response({'detail': 'Academic standards access required.'}, status=403)
        sources = CurriculumSource.objects.filter(school=request.tenant).prefetch_related('versions').order_by('name')
        return Response({'sources': [_source_data(source) for source in sources]})

    @transaction.atomic
    def post(self, request):
        if not _manager(request):
            return Response({'detail': 'School management access required.'}, status=403)
        name = request.data.get('name', '')
        kind = request.data.get('kind')
        jurisdiction = request.data.get('jurisdiction', '')
        authority = request.data.get('authority', '')
        source_url = request.data.get('source_url', '')
        notes = request.data.get('notes', '')
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 180:
            return Response({'name': 'Provide a source name.'}, status=400)
        if kind not in CurriculumSource.Kind.values:
            return Response({'kind': 'Choose a valid source type.'}, status=400)
        if any(not isinstance(v, str) for v in (jurisdiction, authority, source_url, notes)):
            return Response({'detail': 'Check source fields.'}, status=400)
        source = CurriculumSource(
            school=request.tenant, name=name.strip(), kind=kind, jurisdiction=jurisdiction.strip(),
            authority=authority.strip(), source_url=source_url.strip(), notes=notes.strip(), created_by=request.user,
        )
        try:
            source.full_clean()
            source.save()
        except ValidationError as exc:
            return Response(_validation(exc), status=400)
        except IntegrityError:
            return Response({'name': 'A curriculum source with this name already exists.'}, status=409)
        audit(request, 'curriculum.source_created', target=f'curriculum-source:{source.pk}',
              details={'school_id': request.tenant.pk})
        return Response({'source': _source_data(source)}, status=201)


class CurriculumVersionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, source_id):
        if not _manager(request):
            return Response({'detail': 'School management access required.'}, status=403)
        source = CurriculumSource.objects.filter(pk=source_id, school=request.tenant).first()
        if not source:
            return Response({'detail': 'Curriculum source not found.'}, status=404)
        label = request.data.get('label', '')
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 100:
            return Response({'label': 'Provide a version label.'}, status=400)
        version = CurriculumVersion(
            source=source, label=label.strip(), effective_from=request.data.get('effective_from') or None,
            effective_to=request.data.get('effective_to') or None, reference=request.data.get('reference', ''),
            notes=request.data.get('notes', ''), created_by=request.user,
        )
        try:
            version.full_clean()
            if version.effective_from and version.effective_to and version.effective_from > version.effective_to:
                return Response({'effective_to': 'Effective end cannot be before effective start.'}, status=400)
            version.save()
        except ValidationError as exc:
            return Response(_validation(exc), status=400)
        except IntegrityError:
            return Response({'label': 'This source already has that version label.'}, status=409)
        audit(request, 'curriculum.version_created', target=f'curriculum-version:{version.pk}',
              details={'school_id': request.tenant.pk, 'source_id': source.pk})
        return Response({'version': _source_data(source)['versions'][0]}, status=201)


class CurriculumApplicabilityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _school_user(request) or request.user.role not in ('school_admin', 'teacher'):
            return Response({'detail': 'Academic standards access required.'}, status=403)
        rows = CurriculumApplicability.objects.filter(school=request.tenant).select_related(
            'session', 'class_level', 'subject', 'curriculum_version__source'
        ).order_by('-session__start_date', 'class_level__order_index', 'subject__name')
        return Response({'applicability': [{
            'id': row.pk,
            'session': row.session_id,
            'session_name': row.session.name,
            'class_level': row.class_level_id,
            'class_level_name': row.class_level.name,
            'subject': row.subject_id,
            'subject_name': row.subject.name,
            'curriculum_version': row.curriculum_version_id,
            'curriculum_source': row.curriculum_version.source.name,
            'curriculum_version_label': row.curriculum_version.label,
        } for row in rows]})

    @transaction.atomic
    def put(self, request):
        if not _manager(request):
            return Response({'detail': 'School management access required.'}, status=403)
        school = request.tenant
        session = AcademicSession.objects.filter(pk=_positive(request.data.get('session')), school=school).first()
        level = ClassLevel.objects.filter(pk=_positive(request.data.get('class_level')), school=school).first()
        subject = Subject.objects.filter(pk=_positive(request.data.get('subject')), school=school).first()
        version = CurriculumVersion.objects.filter(
            pk=_positive(request.data.get('curriculum_version')), source__school=school
        ).first()
        if not all((session, level, subject, version)):
            return Response({'detail': 'Choose a session, class, subject and curriculum version in this school.'}, status=400)
        row = CurriculumApplicability.objects.filter(
            school=school, session=session, class_level=level, subject=subject
        ).first()
        if row:
            # Once execution exists, changing provenance would rewrite history.
            if CurriculumPlan.objects.filter(school=school, term__session=session, class_level=level, subject=subject).exists():
                if row.curriculum_version_id != version.pk:
                    return Response({'detail': 'This session already has curriculum execution. Preserve its curriculum version.'}, status=409)
                return Response({'id': row.pk, 'curriculum_version': row.curriculum_version_id})
            row.curriculum_version = version
            row.recorded_by = request.user
        else:
            row = CurriculumApplicability(
                school=school, session=session, class_level=level, subject=subject,
                curriculum_version=version, recorded_by=request.user,
            )
        try:
            row.full_clean()
            row.save()
        except ValidationError as exc:
            return Response(_validation(exc), status=400)
        audit(request, 'curriculum.applicability_saved', target=f'curriculum-applicability:{row.pk}',
              details={'school_id': school.pk, 'session_id': session.pk, 'version_id': version.pk})
        return Response({'id': row.pk, 'curriculum_version': row.curriculum_version_id}, status=200)


class AcademicStandardListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _school_user(request) or request.user.role not in ('school_admin', 'teacher'):
            return Response({'detail': 'Academic standards access required.'}, status=403)
        standards = SchoolAcademicStandard.objects.filter(school=request.tenant).select_related(
            'class_level', 'subject', 'curriculum_version__source'
        ).order_by('class_level__order_index', 'subject__name', '-revision')
        if request.user.role in ('teacher', 'class_teacher'):
            assignment_scopes = SubjectAssignment.objects.filter(
                school=request.tenant, teacher__user=request.user, teacher__employment_status='active'
            ).values_list('class_arm__class_level_id', 'subject_id')
            allowed_scopes = set(assignment_scopes)
            standards = [s for s in standards if s.status == SchoolAcademicStandard.Status.APPROVED
                         and (s.class_level_id, s.subject_id) in allowed_scopes]
        return Response({'standards': [_standard_data(s, include_topics=False) for s in standards]})

    @transaction.atomic
    def post(self, request):
        if not _manager(request):
            return Response({'detail': 'School management access required.'}, status=403)
        school = request.tenant
        level = ClassLevel.objects.filter(pk=_positive(request.data.get('class_level')), school=school).first()
        subject = Subject.objects.filter(pk=_positive(request.data.get('subject')), school=school).first()
        version = CurriculumVersion.objects.filter(
            pk=_positive(request.data.get('curriculum_version')), source__school=school
        ).first()
        title = request.data.get('title', '')
        if not all((level, subject, version)) or not isinstance(title, str) or not title.strip():
            return Response({'detail': 'Choose school curriculum scope and provide a title.'}, status=400)
        latest = SchoolAcademicStandard.objects.filter(
            school=school, class_level=level, subject=subject
        ).order_by('-revision').first()
        if latest:
            return Response({'detail': 'Create a new revision from the latest standard instead of another revision 1.'}, status=409)
        standard = SchoolAcademicStandard(
            school=school, curriculum_version=version, class_level=level, subject=subject,
            title=title.strip(), created_by=request.user,
        )
        try:
            standard.full_clean()
            standard.save()
        except ValidationError as exc:
            return Response(_validation(exc), status=400)
        audit(request, 'curriculum.standard_created', target=f'academic-standard:{standard.pk}',
              details={'school_id': school.pk, 'revision': standard.revision})
        return Response({'standard': _standard_data(standard)}, status=201)


class AcademicStandardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, standard_id):
        if not _school_user(request):
            return Response({'detail': 'School access required.'}, status=403)
        standard = SchoolAcademicStandard.objects.filter(pk=standard_id, school=request.tenant).select_related(
            'class_level', 'subject', 'curriculum_version__source'
        ).prefetch_related('topics__objectives').first()
        if not standard or not _teacher_can_read_standard(request, standard):
            return Response({'detail': 'Academic standard not found.'}, status=404)
        return Response({'standard': _standard_data(standard)})


class AcademicStandardTopicCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, standard_id):
        if not _manager(request):
            return Response({'detail': 'School management access required.'}, status=403)
        standard = SchoolAcademicStandard.objects.select_for_update().filter(
            pk=standard_id, school=request.tenant
        ).first()
        if not standard:
            return Response({'detail': 'Academic standard not found.'}, status=404)
        if standard.status != SchoolAcademicStandard.Status.DRAFT:
            return Response({'detail': 'Only a draft academic standard can be edited.'}, status=409)
        term = request.data.get('term')
        title = request.data.get('title', '')
        description = request.data.get('description', '')
        position = _positive(request.data.get('position'))
        week = request.data.get('recommended_week')
        week = _positive(week) if week not in (None, '') else None
        requirement = request.data.get('requirement', AcademicStandardTopic.Requirement.REQUIRED)
        source_reference = request.data.get('source_reference', '')
        objectives = request.data.get('objectives', [])
        if term not in ('first', 'second', 'third') or not isinstance(title, str) or not title.strip():
            return Response({'detail': 'Choose a term and provide a topic title.'}, status=400)
        if not position or position > 200 or (week is not None and week > 52):
            return Response({'detail': 'Choose a valid position and optional recommended week.'}, status=400)
        if requirement not in AcademicStandardTopic.Requirement.values:
            return Response({'requirement': 'Choose required or enrichment.'}, status=400)
        if not isinstance(objectives, list) or len(objectives) > 30 or any(
            not isinstance(value, str) or not value.strip() or len(value.strip()) > 300 for value in objectives
        ):
            return Response({'objectives': 'Provide up to 30 concise objectives.'}, status=400)
        if len({value.strip().casefold() for value in objectives}) != len(objectives):
            return Response({'objectives': 'Duplicate objectives are not allowed.'}, status=400)
        topic = AcademicStandardTopic(
            standard=standard, term=term, title=title.strip(), description=str(description).strip(),
            position=position, recommended_week=week, requirement=requirement,
            source_reference=str(source_reference).strip(),
        )
        try:
            topic.full_clean()
            topic.save()
            AcademicStandardObjective.objects.bulk_create([
                AcademicStandardObjective(topic=topic, text=value.strip(), position=index)
                for index, value in enumerate(objectives, 1)
            ])
        except ValidationError as exc:
            return Response(_validation(exc), status=400)
        except IntegrityError:
            return Response({'position': 'That term already uses this topic position.'}, status=409)
        audit(request, 'curriculum.standard_topic_created', target=f'academic-standard-topic:{topic.pk}',
              details={'school_id': request.tenant.pk, 'standard_id': standard.pk})
        return Response({'topic': topic.pk}, status=201)


class AcademicStandardTransitionView(APIView):
    permission_classes = [IsAuthenticated]
    transitions = {
        SchoolAcademicStandard.Status.DRAFT: ('submit', SchoolAcademicStandard.Status.SUBMITTED),
        SchoolAcademicStandard.Status.SUBMITTED: ('review', SchoolAcademicStandard.Status.REVIEWED),
        SchoolAcademicStandard.Status.REVIEWED: ('approve', SchoolAcademicStandard.Status.APPROVED),
    }

    @transaction.atomic
    def post(self, request, standard_id):
        if not _manager(request):
            return Response({'detail': 'School management access required.'}, status=403)
        standard = SchoolAcademicStandard.objects.select_for_update().filter(
            pk=standard_id, school=request.tenant
        ).prefetch_related('topics__objectives').first()
        if not standard:
            return Response({'detail': 'Academic standard not found.'}, status=404)
        expected = self.transitions.get(standard.status)
        action = request.data.get('action')
        if not expected or action != expected[0]:
            return Response({'detail': f'Invalid transition from {standard.status}.'}, status=409)
        if action == 'submit' and not standard.topics.exists():
            return Response({'detail': 'Add at least one topic before submitting the standard.'}, status=409)
        if action == 'review':
            standard.reviewed_by = request.user
        if action == 'approve':
            if standard.topics.filter(recommended_week__isnull=True).exists():
                return Response({'detail': 'Every topic needs a recommended week before approval.'}, status=409)
            standard.approved_by = request.user
            standard.approved_at = timezone.now()
        standard.status = expected[1]
        standard.save()
        audit_name = {'submit': 'submitted', 'review': 'reviewed', 'approve': 'approved'}[action]
        audit(request, f'curriculum.standard_{audit_name}', target=f'academic-standard:{standard.pk}',
              details={'school_id': request.tenant.pk, 'revision': standard.revision})
        return Response({'standard': _standard_data(standard)})


class AcademicStandardReviseView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, standard_id):
        if not _manager(request):
            return Response({'detail': 'School management access required.'}, status=403)
        previous = SchoolAcademicStandard.objects.select_for_update().filter(
            pk=standard_id, school=request.tenant, status=SchoolAcademicStandard.Status.APPROVED
        ).prefetch_related('topics__objectives').first()
        if not previous:
            return Response({'detail': 'Only an approved standard can start a new revision.'}, status=409)
        if SchoolAcademicStandard.objects.filter(supersedes=previous).exists():
            return Response({'detail': 'A newer revision already exists for this standard.'}, status=409)
        latest_revision = SchoolAcademicStandard.objects.filter(
            school=request.tenant, class_level=previous.class_level, subject=previous.subject
        ).order_by('-revision').values_list('revision', flat=True).first() or previous.revision
        revision = SchoolAcademicStandard.objects.create(
            school=request.tenant, curriculum_version=previous.curriculum_version,
            class_level=previous.class_level, subject=previous.subject, title=previous.title,
            revision=latest_revision + 1, supersedes=previous, created_by=request.user,
        )
        for old_topic in previous.topics.all():
            new_topic = AcademicStandardTopic.objects.create(
                standard=revision, term=old_topic.term, title=old_topic.title,
                description=old_topic.description, position=old_topic.position,
                recommended_week=old_topic.recommended_week, requirement=old_topic.requirement,
                source_reference=old_topic.source_reference,
            )
            AcademicStandardObjective.objects.bulk_create([
                AcademicStandardObjective(topic=new_topic, text=obj.text, position=obj.position)
                for obj in old_topic.objectives.all()
            ])
        audit(request, 'curriculum.standard_revised', target=f'academic-standard:{revision.pk}',
              details={'school_id': request.tenant.pk, 'supersedes': previous.pk, 'revision': revision.revision})
        return Response({'standard': _standard_data(revision)}, status=201)


class AcademicStandardGeneratePlanView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, standard_id):
        if not _manager(request):
            return Response({'detail': 'School management access required.'}, status=403)
        standard = SchoolAcademicStandard.objects.select_for_update().filter(
            pk=standard_id, school=request.tenant, status=SchoolAcademicStandard.Status.APPROVED
        ).select_related('class_level', 'subject', 'curriculum_version').prefetch_related('topics__objectives').first()
        if not standard:
            return Response({'detail': 'Approved academic standard not found.'}, status=404)
        term = Term.objects.filter(
            pk=_positive(request.data.get('term')), session__school=request.tenant
        ).select_related('session').first()
        if not term:
            return Response({'term': 'Choose a term in this school.'}, status=400)
        applicable = CurriculumApplicability.objects.filter(
            school=request.tenant, session=term.session, class_level=standard.class_level,
            subject=standard.subject, curriculum_version=standard.curriculum_version,
        ).exists()
        if not applicable:
            return Response({'detail': 'Pin this curriculum version to the session before generating its scheme.'}, status=409)
        if CurriculumPlan.objects.filter(
            school=request.tenant, term=term, class_level=standard.class_level, subject=standard.subject
        ).exists():
            return Response({'detail': 'A curriculum plan already exists for this term. It will not be overwritten.'}, status=409)
        selected = list(standard.topics.filter(term=term.name).prefetch_related('objectives'))
        if not selected:
            return Response({'detail': 'This standard has no topics for the selected term.'}, status=409)
        if any(topic.recommended_week is None for topic in selected):
            return Response({'detail': 'Every topic needs a recommended week before plan generation.'}, status=409)
        plan = CurriculumPlan.objects.create(
            school=request.tenant, term=term, class_level=standard.class_level, subject=standard.subject
        )
        weeks = {}
        for standard_topic in selected:
            week = weeks.get(standard_topic.recommended_week)
            if not week:
                week = CurriculumWeek.objects.create(plan=plan, number=standard_topic.recommended_week)
                weeks[standard_topic.recommended_week] = week
            position = CurriculumTopic.objects.filter(week=week).count() + 1
            topic = CurriculumTopic.objects.create(
                week=week, title=standard_topic.title, description=standard_topic.description, position=position
            )
            LearningObjective.objects.bulk_create([
                LearningObjective(topic=topic, text=obj.text, position=obj.position)
                for obj in standard_topic.objectives.all()
            ])
        audit(request, 'curriculum.standard_plan_generated', target=f'curriculum-plan:{plan.pk}',
              details={'school_id': request.tenant.pk, 'standard_id': standard.pk, 'term_id': term.pk})
        return Response({'plan': plan.pk, 'standard': standard.pk, 'topics': len(selected)}, status=201)
