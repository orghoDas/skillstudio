from django.db import models
from django.contrib.auth.models import AbstractBaseUser
from django.utils import timezone

# Create your models here.
class User(AbstractBaseUser):
    is_instructor = models.BooleanField(default=False)
    is_student = models.BooleanField(default=True)

    bio = models.TextField(blank=True, null=True)
    profile_picture = models.URLField(blank=True, null=True)
    interests = models.JSONField(default=list)  

    created_at = models.DateTimeField(default=timezone.now)

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null = True)
    action = models.CharField(max_length=255)
    object_type = models.CharField(max_length=100)
    object_id = models.CharField(max_length=100)
    timestamp = models.DateTimeField(default=timezone.now)

    meta = models.JSONField(default=dict)
    