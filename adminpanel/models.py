from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class AdminAction(models.Model):
    """Track all admin actions for audit purposes"""
    ACTION_TYPES = [
        ('user_suspend', 'User Suspended'),
        ('user_activate', 'User Activated'),
        ('user_delete', 'User Deleted'),
        ('course_approve', 'Course Approved'),
        ('course_reject', 'Course Rejected'),
        ('course_delete', 'Course Deleted'),
        ('instructor_approve', 'Instructor Approved'),
        ('instructor_reject', 'Instructor Rejected'),
        ('review_remove', 'Review Removed'),
        ('review_approve', 'Review Approved'),
        ('payment_refund', 'Payment Refunded'),
        ('payout_approve', 'Payout Approved'),
        ('content_flag', 'Content Flagged'),
        ('content_unflag', 'Content Unflagged'),
        ('event_cancel', 'Event Cancelled'),
        ('exam_delete', 'Exam Deleted'),
        ('other', 'Other Action'),
    ]

    admin_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='admin_actions'
    )
    action_type = models.CharField(max_length=50, choices=ACTION_TYPES)
    target_model = models.CharField(max_length=100)  # e.g., 'User', 'Course', 'Payment'
    target_id = models.PositiveIntegerField()
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin_user', '-created_at']),
            models.Index(fields=['action_type', '-created_at']),
            models.Index(fields=['target_model', 'target_id']),
        ]

    def __str__(self):
        return f"{self.admin_user.email if self.admin_user else 'System'} - {self.get_action_type_display()} - {self.created_at}"


class ContentModerationQueue(models.Model):
    """Queue for content that needs moderation"""
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('flagged', 'Flagged for Review'),
    ]

    CONTENT_TYPES = [
        ('course', 'Course'),
        ('review', 'Review'),
        ('forum_post', 'Forum Post'),
        ('thread', 'Discussion Thread'),
        ('event', 'Event'),
    ]

    content_type = models.CharField(max_length=50, choices=CONTENT_TYPES)
    content_id = models.PositiveIntegerField()
    reported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reported_content'
    )
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_content'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['content_type', 'content_id']),
        ]

    def __str__(self):
        return f"{self.get_content_type_display()} #{self.content_id} - {self.get_status_display()}"


class PlatformSettings(models.Model):
    """Global platform settings managed by admins"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    data_type = models.CharField(
        max_length=20,
        choices=[
            ('string', 'String'),
            ('integer', 'Integer'),
            ('float', 'Float'),
            ('boolean', 'Boolean'),
            ('json', 'JSON'),
        ],
        default='string'
    )
    is_public = models.BooleanField(default=False)  # Can be accessed by non-admins
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='updated_settings'
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['key']

    def __str__(self):
        return f"{self.key}: {self.value[:50]}"


class SystemAlert(models.Model):
    """System-wide alerts and announcements"""
    ALERT_TYPES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('maintenance', 'Maintenance'),
    ]

    title = models.CharField(max_length=255)
    message = models.TextField()
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, default='info')
    is_active = models.BooleanField(default=True)
    target_roles = models.JSONField(default=list, blank=True)  # ['student', 'instructor', 'admin'] or empty for all
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_alerts'
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_alert_type_display()})"

    def is_currently_active(self):
        now = timezone.now()
        if not self.is_active:
            return False
        if self.end_time and now > self.end_time:
            return False
        return now >= self.start_time
