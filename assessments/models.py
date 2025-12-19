from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# PostgreSQL Equivalent:
# CREATE TABLE assessments_quiz (
#     id SERIAL PRIMARY KEY,
#     lesson_id INTEGER UNIQUE NOT NULL REFERENCES courses_lesson(id) ON DELETE CASCADE,
#     title VARCHAR(255) DEFAULT '',
#     total_marks INTEGER NOT NULL DEFAULT 0 CHECK (total_marks >= 0),
#     time_limit_minutes INTEGER CHECK (time_limit_minutes >= 0)
# );
# CREATE INDEX assessments_quiz_lesson_id_idx ON assessments_quiz(lesson_id);
class Quiz(models.Model):
    lesson = models.OneToOneField('courses.Lesson', on_delete=models.CASCADE, related_name='quiz')
    title = models.CharField(max_length=255, blank=True)
    total_marks = models.PositiveIntegerField(default=0)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)


# PostgreSQL Equivalent:
# CREATE TABLE assessments_quizquestion (
#     id SERIAL PRIMARY KEY,
#     quiz_id INTEGER NOT NULL REFERENCES assessments_quiz(id) ON DELETE CASCADE,
#     question_text TEXT NOT NULL,
#     question_type VARCHAR(50) NOT NULL DEFAULT 'mcq',
#     difficulty VARCHAR(20) NOT NULL DEFAULT 'medium'
# );
# CREATE INDEX assessments_quizquestion_quiz_id_idx ON assessments_quizquestion(quiz_id);
class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    question_type = models.CharField(max_length=50, default='mcq')
    difficulty = models.CharField(max_length=20, default='medium')


# PostgreSQL Equivalent:
# CREATE TABLE assessments_questionoption (
#     id SERIAL PRIMARY KEY,
#     question_id INTEGER NOT NULL REFERENCES assessments_quizquestion(id) ON DELETE CASCADE,
#     option_text VARCHAR(255) NOT NULL,
#     is_correct BOOLEAN NOT NULL DEFAULT FALSE
# );
# CREATE INDEX assessments_questionoption_question_id_idx ON assessments_questionoption(question_id);
class QuestionOption(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='options')
    option_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)


# PostgreSQL Equivalent:
# CREATE TABLE assessments_quizattempt (
#     id SERIAL PRIMARY KEY,
#     quiz_id INTEGER NOT NULL REFERENCES assessments_quiz(id) ON DELETE CASCADE,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     completed_at TIMESTAMP WITH TIME ZONE,
#     score DECIMAL(8, 2),
#     answers JSONB DEFAULT '{}'
# );
# CREATE INDEX assessments_quizattempt_quiz_user_idx ON assessments_quizattempt(quiz_id, user_id);
class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    answers = models.JSONField(default=dict, blank=True)  

    class Meta:
        indexes = [models.Index(fields=['quiz', 'user'])]


# PostgreSQL Equivalent:
# CREATE TABLE assessments_assignment (
#     id SERIAL PRIMARY KEY,
#     lesson_id INTEGER UNIQUE NOT NULL REFERENCES courses_lesson(id) ON DELETE CASCADE,
#     title VARCHAR(255) DEFAULT '',
#     instructions TEXT DEFAULT '',
#     due_date TIMESTAMP WITH TIME ZONE,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX assessments_assignment_lesson_id_idx ON assessments_assignment(lesson_id);
class Assignment(models.Model):
    lesson = models.OneToOneField('courses.Lesson', on_delete=models.CASCADE, related_name='assignment')
    title = models.CharField(max_length=255, blank=True)
    instructions = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)


# PostgreSQL Equivalent:
# CREATE TABLE assessments_submission (
#     id SERIAL PRIMARY KEY,
#     assignment_id INTEGER NOT NULL REFERENCES assessments_assignment(id) ON DELETE CASCADE,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     file_url TEXT,
#     text TEXT,
#     submitted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     grade DECIMAL(8, 2),
#     feedback TEXT DEFAULT '',
#     graded_at TIMESTAMP WITH TIME ZONE
# );
# CREATE INDEX assessments_submission_assignment_user_idx ON assessments_submission(assignment_id, user_id);
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
