from django.db import models
from django.utils import timezone
from accounts.models import User


class Notification(models.Model):

    TYPES = [
        ("course", "Course Update"),
        ("exam", "Exam Reminder"),
        ("event", "Event Reminder"),
        ("system", "System Message"),
        ("payment", "Payment Update"),
        ("ai", "AI Recommendation"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    notif_type = models.CharField(max_length=20, choices=TYPES)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    metadata = models.JSONField(default=dict)


class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    allow_email = models.BooleanField(default=True)
    allow_sms = models.BooleanField(default=False)
    allow_push = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)
