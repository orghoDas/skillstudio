from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

User = settings.AUTH_USER_MODEL


class Event(models.Model):
    organizer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="organized_events")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, blank=True)
    seats = models.PositiveIntegerField(null=True, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    creted_at = models.DateTimeField(default=timezone.now)


class EventRegistration(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="registrations")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_registrations")
    registered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("event","user")


class LiveClass(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="live_classes")
    host = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="hosted_live_classes")
    scheduled_at = models.DateTimeField()
    meeting_link = models.URLField()
    creaded_at = models.DateTimeField(default=timezone.now)


class LiveMessage(models.Model):
    live_class = models.ForeignKey(LiveClass, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)