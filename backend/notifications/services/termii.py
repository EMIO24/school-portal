import requests
from django.conf import settings
from django.utils import timezone


class TermiiService:

    API_URL = "https://api.ng.termii.com/api/sms/send"

    def send_sms(self, phone, message, sender_id, school=None, template=None, student=None):
        from notifications.models import NotificationLog

        api_key = getattr(settings, 'TERMII_API_KEY', '')

        log = NotificationLog(
            school=school,
            template=template,
            channel='sms',
            recipient_phone=phone,
            student=student,
            message_body=message,
            status='pending',
        )

        payload = {
            'api_key': api_key,
            'to':      phone,
            'from':    sender_id,
            'sms':     message,
            'type':    'plain',
            'channel': 'dnd',
        }

        try:
            resp = requests.post(self.API_URL, json=payload, timeout=15)
            resp.raise_for_status()
            log.status  = 'sent'
            log.sent_at = timezone.now()
            if school:
                log.save()
            return True, ''
        except Exception as exc:
            error_msg = str(exc)
            log.status        = 'failed'
            log.error_message = error_msg
            if school:
                log.save()
            return False, error_msg
