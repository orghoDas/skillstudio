from django.db import models
from django.conf import settings


# skills/models.py
class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=100)


# skills/models.py
class UserSkill(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    proficiency = models.FloatField(default=0.0)

    class Meta:
        unique_together = ("user", "skill")
