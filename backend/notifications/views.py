import hashlib
import json
import uuid
from django.db import transaction
from rest_framework.exceptions import ValidationError
from .models import NotificationBatch, NotificationOutbox
from accounts.school_access import SchoolModulePermission, require_assignment
"""
backend/notifications/views.py

POST /api/notifications/send/
GET  /api/notifications/logs/
GET/POST /api/notifications/templates/
GET/PUT/DELETE /api/notifications/templates/{id}/
"""

from django.utils import timezone
from django.conf import settings
from accounts.permissions import IsSchoolAdmin
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from enrollment.models import StudentProfile, ClassArm
from .models import NotificationTemplate, NotificationLog
from .serializers import NotificationTemplateSerializer, NotificationLogSerializer
from .services.termii import TermiiService
from .services.email import send_email
from .utils import render_template


def _resolve_students(school, recipient_type, class_arm_id=None, student_ids=None):
    qs = StudentProfile.objects.filter(school=school, status='active')
    if recipient_type == 'class' and class_arm_id:
        qs = qs.filter(current_class_id=class_arm_id)
    elif recipient_type == 'individual' and student_ids:
        qs = qs.filter(id__in=student_ids)
    return qs


class NotificationSendView(APIView):
    permission_classes = [IsSchoolAdmin]

    def get(self, request):
        return Response({'capture_only': getattr(settings, 'NOTIFICATIONS_CAPTURE_ONLY', False)})


    @transaction.atomic
    def post(self, request):
        school         = getattr(request, 'tenant', None)
        channel        = request.data.get('channel', 'sms')
        recipient_type = request.data.get('recipient_type', 'individual')
        class_arm_id   = request.data.get('class_arm_id')
        student_ids    = request.data.get('student_ids', [])
        template_id    = request.data.get('template_id')
        raw_message    = request.data.get('message', '')
        raw_subject    = request.data.get('subject', '')

        if channel not in ('sms', 'email', 'both'):
            return Response({'error': 'Choose SMS, email or both.'}, status=400)
        if recipient_type not in ('all_parents', 'class', 'individual'):
            return Response({'error': 'Choose a valid recipient group.'}, status=400)
        if recipient_type == 'class':
            if not str(class_arm_id).isdigit() or not ClassArm.objects.filter(pk=class_arm_id, school=school).exists():
                return Response({'error': 'Select a class in this school.'}, status=400)
        if recipient_type == 'individual':
            if not isinstance(student_ids, list) or not student_ids or any(type(i) is not int for i in student_ids):
                return Response({'error': 'Select at least one student.'}, status=400)
            if StudentProfile.objects.filter(school=school, pk__in=student_ids, status='active').count() != len(set(student_ids)):
                return Response({'error': 'Select active students from this school.'}, status=400)
        if not template_id and (not isinstance(raw_message, str) or not raw_message.strip()):
            return Response({'error': 'Enter a message or select a template.'}, status=400)
        if channel in ('email', 'both') and not template_id and not raw_subject.strip():
            return Response({'error': 'Enter an email subject.'}, status=400)

        template = None
        if template_id:
            try:
                template = NotificationTemplate.objects.get(id=template_id, school=school)
            except NotificationTemplate.DoesNotExist:
                return Response({'error': 'Template not found'}, status=404)

        if template and channel in ('email', 'both') and not template.subject.strip():
            return Response({'error': 'The selected template needs an email subject.'}, status=400)
        students = _resolve_students(school, recipient_type, class_arm_id, student_ids)

        batch_key = request.headers.get('Idempotency-Key') or uuid.uuid4().hex
        if len(batch_key) > 64: raise ValidationError('Invalid request key.')
        digest = hashlib.sha256(json.dumps(request.data, sort_keys=True).encode()).hexdigest()
        batch, created = NotificationBatch.objects.get_or_create(school=school, key=batch_key, defaults={'digest':digest})
        if not created:
            if batch.digest != digest: raise ValidationError('This request key belongs to a different message.')
            return Response({'queued':batch.notificationoutbox_set.count(),'sent':0,'failed':0,'skipped':0,'batch_id':batch.pk}, status=202)
        queued = 0
        termii  = TermiiService()
        sent    = 0
        failed  = 0
        captured = 0
        skipped = 0
        errors = []
        capture_only = getattr(settings, 'NOTIFICATIONS_CAPTURE_ONLY', False)
        sender_id = school.slug[:11] if school else 'SCHOOL'

        for student in students:
            ctx = {
                'student_name': student.user.get_full_name() or student.admission_number,
                'school_name':  school.name if school else '',
                'class_name':   student.current_class.full_name if student.current_class else '',
                'admission_no': student.admission_number,
            }
            body    = render_template(template.body if template else raw_message, ctx)
            subject = template.subject if template else raw_subject

            channels = [channel] if channel != 'both' else ['sms', 'email']

            for ch in channels:
                contact = student.guardian_phone if ch == 'sms' else student.guardian_email
                if not contact:
                    skipped += 1
                    continue
                if capture_only:
                    NotificationLog.objects.create(
                        school=school, template=template, student=student, channel=ch,
                        recipient_phone=contact if ch == 'sms' else '',
                        recipient_email=contact if ch == 'email' else '',
                        message_body=body, status='pending',
                        error_message='Captured locally; no SMS/email was delivered.',
                    )
                    captured += 1
                    continue
                log = NotificationLog.objects.create(school=school, template=template, student=student, channel=ch,
                    recipient_phone=contact if ch == 'sms' else '', recipient_email=contact if ch == 'email' else '',
                    message_body=body, status='pending')
                NotificationOutbox.objects.create(batch=batch, log=log, subject=subject)
                queued += 1

        return Response({'queued':queued, 'batch_id':batch.pk, 'sent': sent, 'failed': failed, 'captured': captured, 'skipped': skipped, 'errors': errors, 'capture_only': capture_only}, status=200 if capture_only else 202)


class NotificationLogListView(APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request):
        school  = getattr(request, 'tenant', None)
        qs      = NotificationLog.objects.filter(school=school)
        status_ = request.query_params.get('status')
        channel = request.query_params.get('channel')
        if status_:
            qs = qs.filter(status=status_)
        if channel:
            qs = qs.filter(channel=channel)
        serializer = NotificationLogSerializer(qs[:100], many=True)
        return Response(serializer.data)


class NotificationTemplateListView(APIView):
    permission_classes = [SchoolModulePermission]

    def get(self, request):
        school = getattr(request, 'tenant', None)
        qs     = NotificationTemplate.objects.filter(school=school)
        return Response(NotificationTemplateSerializer(qs, many=True).data)

    def post(self, request):
        school = getattr(request, 'tenant', None)
        ser    = NotificationTemplateSerializer(data=request.data)
        if ser.is_valid():
            ser.save(school=school)
            return Response(ser.data, status=201)
        return Response(ser.errors, status=400)


class NotificationTemplateDetailView(APIView):
    permission_classes = [SchoolModulePermission]

    def _get(self, pk, school):
        try:
            return NotificationTemplate.objects.get(pk=pk, school=school)
        except NotificationTemplate.DoesNotExist:
            return None

    def get(self, request, pk):
        school = getattr(request, 'tenant', None)
        obj    = self._get(pk, school)
        if not obj:
            return Response(status=404)
        return Response(NotificationTemplateSerializer(obj).data)

    def put(self, request, pk):
        school = getattr(request, 'tenant', None)
        obj    = self._get(pk, school)
        if not obj:
            return Response(status=404)
        ser = NotificationTemplateSerializer(obj, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=400)

    def delete(self, request, pk):
        school = getattr(request, 'tenant', None)
        obj    = self._get(pk, school)
        if not obj:
            return Response(status=404)
        obj.delete()
        return Response(status=204)
