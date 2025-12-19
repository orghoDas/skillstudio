from django.db import models
from django.utils import timezone
from django.conf import settings

User = settings.AUTH_USER_MODEL


# PostgreSQL Equivalent:
# CREATE TABLE notifications_notification (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     title VARCHAR(255),
#     message TEXT NOT NULL,
#     channel VARCHAR(20) NOT NULL DEFAULT 'in_app' CHECK (channel IN ('email', 'sms', 'in_app', 'push')),
#     is_read BOOLEAN NOT NULL DEFAULT FALSE,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX notifications_notification_user_id_idx ON notifications_notification(user_id);
# CREATE INDEX notifications_notification_is_read_idx ON notifications_notification(is_read);
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


# PostgreSQL Equivalent:
# CREATE TABLE notifications_notificationpreference (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER UNIQUE NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     allow_email BOOLEAN NOT NULL DEFAULT TRUE,
#     allow_sms BOOLEAN NOT NULL DEFAULT FALSE,
#     allow_in_app BOOLEAN NOT NULL DEFAULT TRUE,
#     allow_push BOOLEAN NOT NULL DEFAULT TRUE,
#     updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX notifications_notificationpreference_user_id_idx ON notifications_notificationpreference(user_id);
class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    allow_email = models.BooleanField(default=True)
    allow_sms = models.BooleanField(default=False)
    allow_in_app = models.BooleanField(default=True)
    allow_push = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
