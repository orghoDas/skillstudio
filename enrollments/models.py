from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

User = settings.AUTH_USER_MODEL

class Enrollment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='enrollments')
    status  = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    enrolled_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    progress = models.JSONField(default=dict, blank=True)
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'course')   
        indexes = [models.Index(fields=['user', 'course'])]

    def __str__(self):
        return f"{self.user} enrolled in {self.course} - {self.status}"


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='lesson_progress')
    is_completed = models.BooleanField(default=False)
    watch_time = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')
        indexes = [models.Index(fields=['lesson', 'is_completed'])]

    def __str__(self):
        return f'{self.enrollment.user} - {self.lesson.title}'


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlists')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='wishlists')
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'course')

