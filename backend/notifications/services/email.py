import logging
import os

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(to_email, subject, body, school, template=None, student=None):
    from notifications.models import NotificationLog

    api_key    = os.environ.get("BREVO_API_KEY", "")
    from_name  = school.name if school else "School Portal"
    from_email = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@schoolportal.ng")

    log = NotificationLog(
        school=school,
        template=template,
        channel="email",
        recipient_email=to_email,
        student=student,
        message_body=body,
        status="pending",
    )

    if not api_key:
        log.status        = "failed"
        log.error_message = "BREVO_API_KEY not configured"
        log.save()
        logger.error("Brevo email skipped — BREVO_API_KEY not set (school=%s)", getattr(school, "id", None))
        return False, "BREVO_API_KEY not configured"

    payload = {
        "sender":      {"name": from_name, "email": from_email},
        "to":          [{"email": to_email}],
        "subject":     subject,
        "textContent": body,
    }

    try:
        resp = requests.post(
            BREVO_API_URL,
            json=payload,
            headers={
                "api-key":      api_key,
                "Content-Type": "application/json",
                "Accept":       "application/json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        log.status  = "sent"
        log.sent_at = timezone.now()
        log.save()
        return True, ""
    except requests.RequestException as exc:
        error_msg         = str(exc)
        log.status        = "failed"
        log.error_message = error_msg
        log.save()
        logger.exception("Brevo email failed for %s (school=%s)", to_email, getattr(school, "id", None))
        return False, error_msg
