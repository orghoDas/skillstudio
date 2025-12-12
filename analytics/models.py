from django.db import models
from django.conf import settings
# Create your models here.


class CourseAnalyticsSnapshot(models.Model):
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="analytics")
    snapshot_date = models.DateField(auto_now_add=True)
    total_enrollments = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    total_watch_minutes = models.PositiveIntegerField(default=0)
    unique_viewers = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("course", "snapshot_date")


class UserInteraction(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    course = models.ForeignKey("courses.Course", on_delete=models.SET_NULL, null=True)
    event_type = models.ForeignKey("live.Event", on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)