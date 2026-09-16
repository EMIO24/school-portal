"""Durable outbox. Ambiguous provider failures require review, never blind retries."""
from celery import shared_task
from django.db import transaction
from datetime import timedelta
from django.utils import timezone
from .models import NotificationOutbox, NotificationLog

@shared_task
def deliver_outbox():
    import os
    import requests
    from django.conf import settings
    stale_before = timezone.now() - timedelta(minutes=15)
    stale = NotificationOutbox.objects.filter(
        claimed_at__lt=stale_before,
        completed_at__isnull=True,
    )
    NotificationLog.objects.filter(outbox__in=stale).update(
        status='failed',
        error_message='Delivery was claimed by a worker but not completed. Check provider records before resending to avoid duplicates.',
    )
    stale.update(completed_at=timezone.now())

    for pk in NotificationOutbox.objects.filter(claimed_at__isnull=True, completed_at__isnull=True).order_by('pk').values_list('pk', flat=True)[:100]:
        with transaction.atomic():
            # Conditional update is a portable atomic claim on SQLite and PostgreSQL.
            if not NotificationOutbox.objects.filter(pk=pk, claimed_at__isnull=True).update(claimed_at=timezone.now()): continue
        row = NotificationOutbox.objects.select_related('log__school').get(pk=pk)
        log = row.log
        try:
            if log.channel == 'sms':
                key = getattr(settings, 'TERMII_API_KEY', '')
                if not key: raise ValueError('SMS provider is not configured.')
                response = requests.post('https://api.ng.termii.com/api/sms/send', json={'api_key':key,'to':log.recipient_phone,'from':log.school.slug[:11],'sms':log.message_body,'type':'plain','channel':'dnd'}, timeout=15)
            else:
                key = os.environ.get('BREVO_API_KEY','')
                if not key: raise ValueError('Email provider is not configured.')
                response = requests.post('https://api.brevo.com/v3/smtp/email', headers={'api-key':key,'Content-Type':'application/json'}, json={'sender':{'name':log.school.name,'email':os.environ.get('DEFAULT_FROM_EMAIL','noreply@schoolportal.ng')},'to':[{'email':log.recipient_email}],'subject':row.subject,'textContent':log.message_body}, timeout=15)
            response.raise_for_status()
            NotificationLog.objects.filter(pk=log.pk).update(status='sent', sent_at=timezone.now(), error_message='Accepted by provider; delivery to recipient is not yet confirmed.')
        except ValueError as exc:
            NotificationLog.objects.filter(pk=log.pk).update(status='failed', error_message=str(exc))
        except requests.RequestException:
            NotificationLog.objects.filter(pk=log.pk).update(status='failed', error_message='Delivery uncertain or rejected. Check provider records before resending to avoid duplicates.')
        finally:
            NotificationOutbox.objects.filter(pk=pk).update(completed_at=timezone.now())

