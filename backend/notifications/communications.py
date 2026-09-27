"""Manual, portal-first school notices. External notification tools remain separate."""
import hashlib
import json

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import SimpleRateThrottle

from accounts.models import CustomUser, ParentStudentLink
from accounts.permissions import IsSchoolAdmin
from enrollment.models import ClassArm, StaffProfile, StudentProfile, SubjectAssignment
from tenants.models import PlatformEvent
from .models import Communication, CommunicationRecipient


AUDIENCES = {
    'all_parents': 'All linked parents',
    'class_parents': 'Parents of a class',
    'selected_parents': 'Selected parents',
    'all_staff': 'All active staff',
    'class_teachers': 'Teachers of a class',
    'selected_staff': 'Selected staff',
    'all_students': 'All active students',
    'class_students': 'Students of a class',
    'selected_students': 'Selected students',
}


class IsTenantRecipient(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and
                    getattr(request, 'tenant', None) and user.school_id == request.tenant.pk and
                    user.role in ('parent', 'teacher', 'student', 'school_admin'))


class IsActiveSchoolAdmin(IsSchoolAdmin):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.is_active


class NoticePublishThrottle(SimpleRateThrottle):
    rate = '120/hour'

    def get_cache_key(self, request, view):
        return f'notice-publish:{request.tenant.pk}:{request.user.pk}'


def _audience(school, data):
    kind = data.get('audience')
    if not isinstance(kind, str) or kind not in AUDIENCES:
        raise ValueError('Choose a supported audience.')
    class_id = data.get('class_arm_id')
    ids = data.get('recipient_ids', [])
    is_class = kind.startswith('class_')
    is_selected = kind.startswith('selected_')
    if is_class:
        if type(class_id) is not int:
            raise ValueError('Select a class in this school.')
        arm = ClassArm.objects.filter(school=school).select_related('class_level').filter(pk=class_id).first()
        if not arm:
            raise ValueError('Select a class in this school.')
        label = f'{AUDIENCES[kind]}: {arm.full_name}'
    else:
        if class_id is not None:
            raise ValueError('A class is not valid for this audience.')
        label = AUDIENCES[kind]
    if is_selected:
        if not isinstance(ids, list) or not ids or len(ids) > 2000 or any(type(i) is not int or i < 1 for i in ids):
            raise ValueError('Select valid recipient accounts.')
        ids = sorted(set(ids))
    elif ids:
        raise ValueError('Selected recipients are not valid for this audience.')

    missing_links = 0
    users = CustomUser.objects.filter(school=school, is_active=True)
    if kind.endswith('parents'):
        links = ParentStudentLink.objects.filter(school=school, parent__school=school,
            parent__role='parent', parent__is_active=True, student__school=school,
            student__status='active')
        if kind == 'class_parents':
            links = links.filter(student__current_class_id=class_id)
        linked_ids = links.values_list('parent_id', flat=True).distinct()
        users = users.filter(role='parent', pk__in=linked_ids)
        if is_selected:
            users = users.filter(pk__in=ids)
        if kind == 'class_parents':
            missing_links = StudentProfile.objects.filter(school=school, status='active',
                current_class_id=class_id).exclude(parent_links__in=links).count()
    elif kind.endswith('staff') or kind == 'class_teachers':
        users = users.filter(role__in=('teacher', 'school_admin'), staff_profile__school=school,
            staff_profile__employment_status='active')
        if kind == 'class_teachers':
            assigned = SubjectAssignment.objects.filter(school=school, class_arm_id=class_id,
                term__is_current=True, term__session__school=school).values_list('teacher__user_id', flat=True)
            staff_assigned = StaffProfile.objects.filter(school=school, assigned_classes__id=class_id).values_list('user_id', flat=True)
            arm_teacher = ClassArm.objects.filter(school=school, pk=class_id).values_list('class_teacher_id', flat=True)
            users = users.filter(Q(pk__in=assigned) | Q(pk__in=staff_assigned) | Q(pk__in=arm_teacher), role='teacher')
        if is_selected:
            users = users.filter(pk__in=ids)
    else:
        users = users.filter(role='student', student_profile__school=school, student_profile__status='active')
        if kind == 'class_students':
            users = users.filter(student_profile__current_class_id=class_id)
        if is_selected:
            users = users.filter(pk__in=ids)
    if is_selected and users.values('pk').distinct().count() != len(ids):
        raise ValueError('Select active recipient accounts in this school and audience.')
    recipients = list(users.order_by('pk').values('pk', 'first_name', 'last_name').distinct()[:2001])
    if len(recipients) > 2000:
        raise ValueError('Audience is too large for one manual notice.')
    return kind, label, recipients, missing_links


class NoticePagination(PageNumberPagination):
    page_size = 20
    max_page_size = 20


class AudiencePreview(APIView):
    permission_classes = [IsActiveSchoolAdmin]

    def post(self, request):
        try:
            kind, label, recipients, missing = _audience(request.tenant, request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'audience': kind, 'label': label, 'recipient_count': len(recipients),
                         'students_without_linked_parent': missing, 'channel': 'portal',
                         'external_channels': 'Use the existing Notifications tool separately for email or SMS.'})


class RecipientOptions(APIView):
    permission_classes = [IsActiveSchoolAdmin]

    def get(self, request):
        kind = request.query_params.get('audience')
        if kind not in ('selected_parents', 'selected_staff', 'selected_students'):
            return Response({'detail': 'Choose a selected-recipient audience.'}, status=400)
        school = request.tenant
        users = CustomUser.objects.filter(school=school, is_active=True)
        if kind == 'selected_parents':
            linked = ParentStudentLink.objects.filter(school=school, parent__school=school,
                student__school=school, student__status='active').values_list('parent_id', flat=True)
            users = users.filter(role='parent', pk__in=linked)
        elif kind == 'selected_staff':
            users = users.filter(role__in=('teacher', 'school_admin'), staff_profile__school=school,
                                 staff_profile__employment_status='active')
        else:
            users = users.filter(role='student', student_profile__school=school,
                                 student_profile__status='active')
        search = request.query_params.get('search', '').strip()[:80]
        if search:
            users = users.filter(Q(first_name__icontains=search) | Q(last_name__icontains=search))
        rows = users.order_by('first_name', 'last_name', 'pk').values('pk', 'first_name', 'last_name').distinct()[:50]
        return Response([{'id': r['pk'], 'name': f"{r['first_name']} {r['last_name']}".strip()} for r in rows])


class NoticeSend(APIView):
    permission_classes = [IsActiveSchoolAdmin]
    throttle_classes = [NoticePublishThrottle]

    @transaction.atomic
    def post(self, request):
        key = request.headers.get('Idempotency-Key', '')
        if not key or len(key) > 64 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in key):
            return Response({'detail': 'A valid Idempotency-Key is required.'}, status=400)
        title, body = request.data.get('title'), request.data.get('body')
        if not isinstance(title, str) or not title.strip() or len(title.strip()) > 160:
            return Response({'detail': 'Enter a title of up to 160 characters.'}, status=400)
        if not isinstance(body, str) or not body.strip() or len(body.strip()) > 5000:
            return Response({'detail': 'Enter a message of up to 5000 characters.'}, status=400)
        if request.data.get('channels', ['portal']) != ['portal']:
            return Response({'detail': 'This centre publishes portal notices only. Use Notifications for external channels.'}, status=400)
        recipient_ids = request.data.get('recipient_ids', [])
        if not isinstance(recipient_ids, list) or any(type(i) is not int for i in recipient_ids):
            return Response({'detail': 'Select valid recipient accounts.'}, status=400)
        payload = {'title': title.strip(), 'body': body.strip(), 'audience': request.data.get('audience'),
                   'class_arm_id': request.data.get('class_arm_id'),
                   'recipient_ids': sorted(set(recipient_ids))}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        existing = Communication.objects.filter(school=request.tenant, key=key).first()
        if existing:
            if existing.digest != digest:
                return Response({'detail': 'This request key was used for a different notice.'}, status=409)
            return Response({'id': existing.pk, 'recipient_count': existing.recipient_count,
                             'status': 'available_in_portal', 'replayed': True})
        try:
            kind, label, recipients, _ = _audience(request.tenant, request.data)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        if not recipients:
            return Response({'detail': 'No active portal accounts are linked to this audience.'}, status=400)
        notice, created = Communication.objects.get_or_create(school=request.tenant, key=key,
            defaults={'sender': request.user, 'sender_name': request.user.full_name,
                      'title': payload['title'], 'body': payload['body'], 'audience': kind,
                      'audience_label': label, 'recipient_count': len(recipients), 'digest': digest})
        if not created:
            if notice.digest != digest:
                return Response({'detail': 'This request key was used for a different notice.'}, status=409)
            return Response({'id': notice.pk, 'recipient_count': notice.recipient_count,
                             'status': 'available_in_portal', 'replayed': True})
        CommunicationRecipient.objects.bulk_create([
            CommunicationRecipient(communication=notice, user_id=row['pk'],
                recipient_name=f"{row['first_name']} {row['last_name']}".strip()) for row in recipients
        ])
        PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email,
            action='school.communication_published', target=str(notice.pk),
            details={'school_id': request.tenant.pk, 'audience': kind, 'recipient_count': len(recipients)})
        return Response({'id': notice.pk, 'recipient_count': len(recipients),
                         'status': 'available_in_portal', 'replayed': False}, status=201)


def _history_row(notice):
    return {'id': notice.pk, 'title': notice.title, 'audience': notice.audience,
            'audience_label': notice.audience_label, 'sender_name': notice.sender_name,
            'published_at': notice.published_at, 'recipient_count': notice.recipient_count,
            'read_count': notice.read_count, 'channel': 'portal', 'status': 'available_in_portal'}


class NoticeHistory(APIView):
    permission_classes = [IsActiveSchoolAdmin]

    def get(self, request):
        qs = Communication.objects.filter(school=request.tenant).annotate(
            read_count=Count('recipients', filter=Q(recipients__read_at__isnull=False))).order_by('-published_at', '-pk')
        audience = request.query_params.get('audience')
        if audience:
            if audience not in AUDIENCES:
                return Response({'detail': 'Invalid audience filter.'}, status=400)
            qs = qs.filter(audience=audience)
        pager = NoticePagination()
        page = pager.paginate_queryset(qs, request)
        return pager.get_paginated_response([_history_row(n) for n in page])


class NoticeHistoryDetail(APIView):
    permission_classes = [IsActiveSchoolAdmin]

    def get(self, request, pk):
        notice = get_object_or_404(Communication.objects.filter(school=request.tenant).annotate(
            read_count=Count('recipients', filter=Q(recipients__read_at__isnull=False))), pk=pk)
        return Response({**_history_row(notice), 'body': notice.body})


class NoticeInbox(APIView):
    permission_classes = [IsTenantRecipient]

    def get(self, request):
        qs = CommunicationRecipient.objects.filter(user=request.user,
            communication__school=request.tenant).select_related('communication').order_by('-communication__published_at', '-pk')
        pager = NoticePagination()
        page = pager.paginate_queryset(qs, request)
        return pager.get_paginated_response([{
            'id': row.pk, 'title': row.communication.title, 'body': row.communication.body,
            'sender_name': row.communication.sender_name, 'published_at': row.communication.published_at,
            'read_at': row.read_at, 'status': 'read' if row.read_at else 'available_in_portal',
        } for row in page])


class NoticeRead(APIView):
    permission_classes = [IsTenantRecipient]

    def post(self, request, pk):
        row = get_object_or_404(CommunicationRecipient, pk=pk, user=request.user,
                                communication__school=request.tenant)
        if row.read_at is None:
            CommunicationRecipient.objects.filter(pk=row.pk, read_at__isnull=True).update(read_at=timezone.now())
            row.refresh_from_db(fields=['read_at'])
        return Response({'id': row.pk, 'read_at': row.read_at, 'status': 'read'})
