"""
backend/notifications/views.py

POST /api/notifications/send/
GET  /api/notifications/logs/
GET/POST /api/notifications/templates/
GET/PUT/DELETE /api/notifications/templates/{id}/
"""

from django.utils import timezone
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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        school         = getattr(request, 'tenant', None)
        channel        = request.data.get('channel', 'sms')
        recipient_type = request.data.get('recipient_type', 'individual')
        class_arm_id   = request.data.get('class_arm_id')
        student_ids    = request.data.get('student_ids', [])
        template_id    = request.data.get('template_id')
        raw_message    = request.data.get('message', '')
        raw_subject    = request.data.get('subject', '')

        template = None
        if template_id:
            try:
                template = NotificationTemplate.objects.get(id=template_id, school=school)
            except NotificationTemplate.DoesNotExist:
                return Response({'error': 'Template not found'}, status=404)

        students = _resolve_students(school, recipient_type, class_arm_id, student_ids)

        termii  = TermiiService()
        sent    = 0
        failed  = 0
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
                if ch == 'sms' and student.guardian_phone:
                    ok, _ = termii.send_sms(
                        student.guardian_phone, body, sender_id,
                        school=school, template=template, student=student,
                    )
                    sent += 1 if ok else 0
                    failed += 0 if ok else 1

                elif ch == 'email' and student.guardian_email:
                    ok, _ = send_email(
                        student.guardian_email, subject, body, school,
                        template=template, student=student,
                    )
                    sent += 1 if ok else 0
                    failed += 0 if ok else 1

        return Response({'sent': sent, 'failed': failed})


class NotificationLogListView(APIView):
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

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
