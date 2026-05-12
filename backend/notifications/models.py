from django.db import models


class NotificationTemplate(models.Model):
    TYPE_CHOICES = [
        ('sms',   'SMS'),
        ('email', 'Email'),
        ('both',  'Both'),
    ]
    CATEGORY_CHOICES = [
        ('result',     'Result'),
        ('fee',        'Fee'),
        ('attendance', 'Attendance'),
        ('exam',       'Exam'),
        ('general',    'General'),
    ]

    school     = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='notification_templates')
    name       = models.CharField(max_length=120)
    type       = models.CharField(max_length=10, choices=TYPE_CHOICES)
    subject    = models.CharField(max_length=200, blank=True)
    body       = models.TextField()
    category   = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_type_display()}) — {self.school.name}"


class NotificationLog(models.Model):
    STATUS_CHOICES = [
        ('sent',    'Sent'),
        ('failed',  'Failed'),
        ('pending', 'Pending'),
    ]
    CHANNEL_CHOICES = [
        ('sms',   'SMS'),
        ('email', 'Email'),
    ]

    school           = models.ForeignKey('tenants.School', on_delete=models.CASCADE, related_name='notification_logs')
    template         = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs')
    channel          = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    recipient_phone  = models.CharField(max_length=20, blank=True)
    recipient_email  = models.CharField(max_length=200, blank=True)
    student          = models.ForeignKey('enrollment.StudentProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='notification_logs')
    message_body     = models.TextField()
    status           = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    sent_at          = models.DateTimeField(null=True, blank=True)
    error_message    = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.channel.upper()} → {self.recipient_phone or self.recipient_email} [{self.status}]"
