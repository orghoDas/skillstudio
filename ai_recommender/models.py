from django.db import models
from accounts.models import User
from courses.models import Course

# Create your models here.

class SkillProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    skills = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

class AIRecommendation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)

    score = models.FloatField()
    explanation = models.TextField()
    generated_at = models.DateTimeField(auto_now_add=True)