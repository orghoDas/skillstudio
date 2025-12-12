from django.db import models
from accounts.models import User
from django.utils import timezone
from courses.models import Course

# Create your models here.

class QuestionBank(models.Model):
    DIFFICULTIES = [
        (easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    question_text = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    options = models.JSONField()  # Storing options as a JSON object
    correct_answer = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)

class Exam(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    duration_minutes = models.IntegerField()

    created_at = models.DateTimeField(default=timezone.now)

class ExamAttempt(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.FloatField()
    answers = models.JSONField(default=dict)

    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True) 

