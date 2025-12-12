from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class Quiz(models.Model):
    lesson = models.OneToOneField('courses.Lesson', on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=255, blank=True)
    total_marks = models.PositiveIntegerField(default=0)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)

class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=50, default='mcq')
    difficulty = models.CharField(max_length=20, default='medium')


class QuestionOption(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    answers = models.JSONField(default=dict, blank=True)  

    class Meta:
        indexes = [models.Index(fields=['quiz', 'user'])]


class Assignment(models.Model):
    lesson = models.OneToOneField('courses.Lesson', on_delete=models.CASCADE, related_name='assignment')
    title = models.CharField(max_length=255, blank=True)
    instructions = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)


class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file_url = models.TextField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    grade = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [models.Index(fields=['assignment', 'user'])]
