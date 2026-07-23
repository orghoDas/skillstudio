from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


# =========================
# QUIZ (Lesson-level)
# =========================

class Quiz(models.Model):
    lesson = models.OneToOneField(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='quiz'
    )
    title = models.CharField(max_length=255, blank=True)
    total_marks = models.PositiveIntegerField(default=0)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    passing_percentage = models.PositiveIntegerField(default=50)
    is_published = models.BooleanField(default=True)

    def has_time_limit(self):
        return bool(self.time_limit_minutes)

# PostgreSQL equivalent:
# CREATE TABLE IF NOT EXISTS assessments_quiz (
#     id serial PRIMARY KEY,
#     lesson_id integer NOT NULL UNIQUE REFERENCES courses_lesson(id) ON DELETE CASCADE,
#     title varchar(255) NOT NULL DEFAULT '',
#     total_marks integer NOT NULL DEFAULT 0,
#     time_limit_minutes integer NULL,
#     passing_percentage integer NOT NULL DEFAULT 50,
#     is_published boolean NOT NULL DEFAULT true
# );

class QuizAttempt(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    score = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    answers = models.JSONField(default=dict)
    question_snapshot = models.JSONField(default=list, blank=True)
    total_marks_snapshot = models.PositiveIntegerField(default=0)
    passed = models.BooleanField(default=False)

    is_auto_submitted = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["quiz", "user"],
                name="uniq_quiz_attempt_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["quiz", "user"]),
            models.Index(fields=["completed_at"])
        ]

    def time_remaining_seconds(self):
        if not self.quiz.time_limit_minutes:
            return None

        elapsed = (timezone.now() - self.started_at).total_seconds()
        limit = self.quiz.time_limit_minutes * 60
        return max(0, int(limit - elapsed))

    def is_expired(self):
        remaining = self.time_remaining_seconds()
        return remaining == 0

# PostgreSQL equivalent for attempts:
# CREATE TABLE IF NOT EXISTS assessments_quizattempt (
#     id serial PRIMARY KEY,
#     quiz_id integer NOT NULL REFERENCES assessments_quiz(id) ON DELETE CASCADE,
#     user_id integer NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
#     started_at timestamptz NOT NULL DEFAULT now(),
#     completed_at timestamptz NULL,
#     score numeric(8,2) NULL,
#     answers jsonb NOT NULL DEFAULT '{}',
#     question_snapshot jsonb NOT NULL DEFAULT '[]',
#     total_marks_snapshot integer NOT NULL DEFAULT 0,
#     passed boolean NOT NULL DEFAULT false,
#     is_auto_submitted boolean NOT NULL DEFAULT false
# );
# CREATE INDEX IF NOT EXISTS idx_assessments_quizattempt_quiz_user ON assessments_quizattempt (quiz_id, user_id);
# CREATE INDEX IF NOT EXISTS idx_assessments_quizattempt_completed_at ON assessments_quizattempt (completed_at);
class QuizQuestion(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions"
    )
    question_text = models.TextField()
    difficulty = models.CharField(
        max_length=20,
        default="medium"
    )
    marks = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.question_text[:60]

# PostgreSQL equivalent for questions:
# CREATE TABLE IF NOT EXISTS assessments_quizquestion (
#     id serial PRIMARY KEY,
#     quiz_id integer NOT NULL REFERENCES assessments_quiz(id) ON DELETE CASCADE,
#     question_text text NOT NULL,
#     difficulty varchar(20) NOT NULL DEFAULT 'medium',
#     marks integer NOT NULL DEFAULT 1
# );

class QuestionOption(models.Model):
    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name="options"
    )
    option_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.option_text

# PostgreSQL equivalent for question options:
# CREATE TABLE IF NOT EXISTS assessments_questionoption (
#     id serial PRIMARY KEY,
#     question_id integer NOT NULL REFERENCES assessments_quizquestion(id) ON DELETE CASCADE,
#     option_text varchar(255) NOT NULL,
#     is_correct boolean NOT NULL DEFAULT false
# );
