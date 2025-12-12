from django.db import models
from django.utils import timezone
from accounts.models import User
# Create your models here.

class Course(models.Model):
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    title = models.CharField(max_length=255)
    description = models.TextField()
    thumbnail = models.URLField(blank=True, null=True)

    category = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    is_published = models.BooleanField(default=False)

    version = models.IntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)


class CourseVersion(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    version_number = models.IntegerField()
    data = models.JSONField()  
    created_at = models.DateTimeField(default=timezone.now)


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    order = models.IntegerField()

    created_at = models.DateTimeField(default=timezone.now)

class Lesson(models.Model):
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    video_url = models.URLField(blank=True, null=True)
    content = models.TextField()
    order = models.IntegerField()

    created_at = models.DateTimeField(default=timezone.now)


class Resources(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources')
    resource_type = models.CharField(max_length=100)  
    file_url = models.URLField()

    created_at = models.DateTimeField(default=timezone.now)

class CourseEnrollment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    progress = models.JSONField(default=dict)
    enrolled_on = models.DateTimeField(default=timezone.now)