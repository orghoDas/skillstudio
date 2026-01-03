from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from decimal import Decimal

from accounts.models import User
from courses.models import Course


class Event(models.Model):
    """
    Live workshops, webinars, and events.
    Can be standalone or tied to a course.
    """
    EVENT_TYPES = [
        ('workshop', 'Workshop'),
        ('webinar', 'Webinar'),
        ('masterclass', 'Masterclass'),
        ('networking', 'Networking'),
        ('qa', 'Q&A Session'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    
    # Basic Information
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_events')
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='webinar')
    
    # Cover image
    cover_image = models.ImageField(upload_to='events/covers/', null=True, blank=True)
    
    # Scheduling
    scheduled_for = models.DateTimeField()
    duration_minutes = models.IntegerField(validators=[MinValueValidator(15)], default=60)
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Capacity & Pricing
    max_seats = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    is_free = models.BooleanField(default=True)
    
    # Access & Requirements
    requires_enrollment = models.BooleanField(default=False)  # Require course enrollment
    prerequisites = models.TextField(blank=True)
    
    # Meeting Details
    meeting_link = models.URLField(blank=True)
    meeting_password = models.CharField(max_length=100, blank=True)
    platform = models.CharField(max_length=50, blank=True)  # Zoom, Google Meet, etc.
    
    # Status & Publishing
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    is_featured = models.BooleanField(default=False)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_for']
        indexes = [
            models.Index(fields=['scheduled_for', 'status']),
            models.Index(fields=['host']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.scheduled_for.strftime('%Y-%m-%d %H:%M')}"
    
    def is_past(self):
        """Check if event is in the past."""
        return timezone.now() > self.scheduled_for
    
    def is_upcoming(self):
        """Check if event is upcoming."""
        return timezone.now() < self.scheduled_for
    
    def seats_available(self):
        """Get number of available seats."""
        if not self.max_seats:
            return None
        registered_count = self.registrations.filter(status='confirmed').count()
        return max(0, self.max_seats - registered_count)
    
    def available_seats(self):
        """Alias for seats_available()."""
        return self.seats_available()
    
    def is_full(self):
        """Check if event is full."""
        if not self.max_seats:
            return False
        return self.seats_available() == 0
    
    def attendee_count(self):
        """Get number of confirmed attendees."""
        return self.registrations.filter(status='confirmed').count()


class EventRegistration(models.Model):
    """
    User registration for events.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('attended', 'Attended'),
        ('no_show', 'No Show'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_registrations')
    
    # Payment (if event is paid)
    payment_status = models.CharField(max_length=20, default='pending')
    payment_amount = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='confirmed')
    
    # Attendance tracking
    attended = models.BooleanField(default=False)
    attended_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    registered_on = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['event', 'user']]
        ordering = ['-registered_on']
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.event.title}"


class EventFeedback(models.Model):
    """
    Post-event feedback and ratings.
    """
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='feedbacks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_feedbacks')
    
    # Rating
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    
    # Feedback
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    
    # Specific ratings
    content_quality = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    host_performance = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], null=True, blank=True)
    would_recommend = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['event', 'user']]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.event.title} ({self.rating}★)"


class EventAttendanceLog(models.Model):
    """
    Track when users join/leave events for analytics.
    """
    registration = models.ForeignKey(EventRegistration, on_delete=models.CASCADE, related_name='attendance_logs')
    
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.registration.user.email} - {self.registration.event.title}"


class EventResource(models.Model):
    """
    Resources shared during or after events.
    """
    RESOURCE_TYPES = [
        ('slides', 'Presentation Slides'),
        ('recording', 'Recording'),
        ('handout', 'Handout'),
        ('link', 'External Link'),
        ('file', 'File'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='resources')
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    
    # File or link
    file = models.FileField(upload_to='events/resources/', null=True, blank=True)
    url = models.URLField(blank=True)
    
    # Access control
    available_after_event = models.BooleanField(default=True)
    attendees_only = models.BooleanField(default=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.title} - {self.event.title}"
