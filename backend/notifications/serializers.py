from rest_framework import serializers
from .models import NotificationTemplate, NotificationLog


class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = NotificationTemplate
        fields = ['id', 'name', 'type', 'subject', 'body', 'category', 'created_at']
        read_only_fields = ['created_at']


class NotificationLogSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model  = NotificationLog
        fields = [
            'id', 'channel', 'recipient_phone', 'recipient_email',
            'student', 'student_name', 'message_body', 'status',
            'sent_at', 'error_message', 'created_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        if obj.student:
            return obj.student.user.get_full_name() or obj.student.admission_number
        return ''
