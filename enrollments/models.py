from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(default=timezone.now)
    progress = models.JSONField(default=dict, blank=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'course')   
        indexes = [models.Index(fields=['course', 'user'])]


class LessonProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='lesson_progress')
    is_completed = models.BooleanField(default=False)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'lesson')
        indexes = [models.Index(fields=['user', 'lesson'])]


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlists')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='wishlists')
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'course')

