from django.db import models
from accounts.models import User
from django.utils import timezone
from courses.models import Course

# Create your models here.


# PostgreSQL Equivalent:
# CREATE TABLE exams_questionbank (
#     id SERIAL PRIMARY KEY,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     question_text TEXT NOT NULL,
#     difficulty VARCHAR(10) NOT NULL CHECK (difficulty IN ('easy', 'medium', 'hard')),
#     options JSONB NOT NULL,
#     correct_answer VARCHAR(255) NOT NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX exams_questionbank_course_id_idx ON exams_questionbank(course_id);
# CREATE INDEX exams_questionbank_difficulty_idx ON exams_questionbank(difficulty);
class QuestionBank(models.Model):
    DIFFICULTIES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    question_text = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTIES)
    options = models.JSONField()  # Storing options as a JSON object
    correct_answer = models.CharField(max_length=255)

    created_at = models.DateTimeField(auto_now_add=True)


# PostgreSQL Equivalent:
# CREATE TABLE exams_exam (
#     id SERIAL PRIMARY KEY,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     title VARCHAR(255) NOT NULL,
#     duration_minutes INTEGER NOT NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX exams_exam_course_id_idx ON exams_exam(course_id);
class Exam(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    duration_minutes = models.IntegerField()

    created_at = models.DateTimeField(default=timezone.now)


# PostgreSQL Equivalent:
# CREATE TABLE exams_examattempt (
#     id SERIAL PRIMARY KEY,
#     exam_id INTEGER NOT NULL REFERENCES exams_exam(id) ON DELETE CASCADE,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     score DOUBLE PRECISION NOT NULL,
#     answers JSONB DEFAULT '{}',
#     started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     completed_at TIMESTAMP WITH TIME ZONE
# );
# CREATE INDEX exams_examattempt_exam_id_idx ON exams_examattempt(exam_id);
# CREATE INDEX exams_examattempt_user_id_idx ON exams_examattempt(user_id);
class ExamAttempt(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    score = models.FloatField()
    answers = models.JSONField(default=dict)

    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True) 
