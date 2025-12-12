from django.db import models
from django.utils import timezone
from django.conf import settings

User = settings.AUTH_USER_MODEL


class Notification(models.Model):
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('in_app', 'In-App'),
        ('push', 'Push Notification')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255, blank=True, null=True)
    message = models.TextField()
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default='in_app')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)


class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    allow_email = models.BooleanField(default=True)
    allow_sms = models.BooleanField(default=False)
    allow_in_app = models.BooleanField(default=True)
    allow_push = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
