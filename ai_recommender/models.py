from django.db import models
from django.conf import settings

# Create your models here.

class SkillProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    skills = models.JSONField(default=list, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

class Recommendation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations")
    score = models.FloatField()
    reason = models.TextField(blank=True, null=True)
    model_version = models.CharField(max_length=50, blank=True, null=True)
    recommended_course = models.ForeignKey("courses.Course", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class Embedding(models.Model):
    entity_type = models.CharField(max_length=50)
    entity_id = models.BigIntegerField()
    vector = models.BinaryField()
    meta = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

