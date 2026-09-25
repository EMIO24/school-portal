"""Restricted edits to the existing account attached to a school profile."""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from rest_framework import serializers
from tenants.models import PlatformEvent


def edit_account(request, user, changes):
    allowed = {'first_name', 'last_name', 'email', 'is_active', 'phone_number'}
    if set(changes) - allowed or user.school_id != request.tenant.pk:
        raise serializers.ValidationError('Select an account from this school.')
    if 'email' in changes:
        changes['email'] = changes['email'].strip().lower() or None
        if not changes['email'] and user.role != 'student':
            raise serializers.ValidationError({'new_email': 'Email is required.'})
        if changes['email'] and get_user_model().objects.filter(email__iexact=changes['email']).exclude(pk=user.pk).exists():
            raise serializers.ValidationError({'new_email': 'This email cannot be used. Check the account details.'})
    if changes.get('is_active') is False and user.pk == request.user.pk:
        raise serializers.ValidationError('Ask another administrator to deactivate your account.')
    for key, value in changes.items():
        setattr(user, key, value)
    if not changes:
        return
    try:
        with transaction.atomic():
            user.save(update_fields=list(changes))
    except IntegrityError:
        raise serializers.ValidationError('These account details cannot be used. Check for duplicates.')
    PlatformEvent.objects.create(actor=request.user, actor_email=request.user.email,
        action='school.account_updated', target=str(user.pk),
        details={'school_id':user.school_id, 'fields':list(changes)})


def account_changes(data):
    return {key.removeprefix('new_'):data.pop(key) for key in
        ('new_first_name','new_last_name','new_email') if key in data}
