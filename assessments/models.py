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
    passed = models.BooleanField(default=False)

    is_auto_submitted = models.BooleanField(default=False)

    class Meta:
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
#     passed boolean NOT NULL DEFAULT false,
#     is_auto_submitted boolean NOT NULL DEFAULT false
# );
# CREATE INDEX IF NOT EXISTS idx_assessments_quizattempt_quiz_user ON assessments_quizattempt (quiz_id, user_id);
# CREATE INDEX IF NOT EXISTS idx_assessments_quizattempt_completed_at ON assessments_quizattempt (completed_at);
class QuizQuestion(models.Model):
    MCQ = "mcq"
    TRUE_FALSE = "tf"

    QUESTION_TYPES = [
        (MCQ, "Multiple Choice"),
        (TRUE_FALSE, "True / False"),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions"
    )
    question_text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=QUESTION_TYPES,
        default=MCQ
    )
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
#     question_type varchar(20) NOT NULL DEFAULT 'mcq',
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

# =========================
# ASSIGNMENTS (Manual grading)
# =========================

class Assignment(models.Model):
    lesson = models.OneToOneField(
        "courses.Lesson",
        on_delete=models.CASCADE,
        related_name="assignment"
    )
    title = models.CharField(max_length=255, blank=True)
    instructions = models.TextField(blank=True)
    due_date = models.DateTimeField(null=True, blank=True)

    max_score = models.PositiveIntegerField(default=100)

    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title or f"Assignment for {self.lesson.title}"

# PostgreSQL equivalent for assignments:
# CREATE TABLE IF NOT EXISTS assessments_assignment (
#     id serial PRIMARY KEY,
#     lesson_id integer NOT NULL UNIQUE REFERENCES courses_lesson(id) ON DELETE CASCADE,
#     title varchar(255) NOT NULL DEFAULT '',
#     instructions text NOT NULL DEFAULT '',
#     due_date timestamptz NULL,
#     max_score integer NOT NULL DEFAULT 100,
#     created_at timestamptz NOT NULL DEFAULT now()
# );

class Submission(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    file_url = models.TextField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)

    submitted_at = models.DateTimeField(default=timezone.now)

    grade = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )
    feedback = models.TextField(blank=True)

    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="graded_submissions"
    )

    class Meta:
        unique_together = ("assignment", "user")
        indexes = [
            models.Index(fields=["assignment", "user"]),
        ]

    def __str__(self):
        return f"{self.user} – {self.assignment}"
    

# PostgreSQL equivalent for submissions:
# CREATE TABLE IF NOT EXISTS assessments_submission (
#     id serial PRIMARY KEY,
#     assignment_id integer NOT NULL REFERENCES assessments_assignment(id) ON DELETE CASCADE,
#     user_id integer NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
#     file_url text NULL,
#     text text NULL,
#     submitted_at timestamptz NOT NULL DEFAULT now(),
#     grade numeric(8,2) NULL,
#     feedback text NOT NULL DEFAULT '',
#     graded_at timestamptz NULL,
#     graded_by_id integer NULL REFERENCES auth_user(id) ON DELETE SET NULL,
#     UNIQUE (assignment_id, user_id)
# );
# CREATE INDEX IF NOT EXISTS idx_assessments_submission_assignment_user ON assessments_submission (assignment_id, user_id);

class Rubric(models.Model):
    assignment = models.OneToOneField(
        'Assignment',
        on_delete=models.CASCADE,
        related_name='rubric'
    )
    total_marks = models.DecimalField(max_digits=6, decimal_places=2)
    criteria = models.JSONField()
    # Example:
    # [
    #   {"key": "clarity", "label": "Clarity", "max": 20},
    #   {"key": "accuracy", "label": "Accuracy", "max": 30}
    # ]

    created_at = models.DateTimeField(default=timezone.now)

# PostgreSQL equivalent for rubric:
# CREATE TABLE IF NOT EXISTS assessments_rubric (
#     id serial PRIMARY KEY,
#     assignment_id integer NOT NULL UNIQUE REFERENCES assessments_assignment(id) ON DELETE CASCADE,
#     total_marks numeric(6,2) NOT NULL,
#     criteria jsonb NOT NULL,
#     created_at timestamptz NOT NULL DEFAULT now()
# );
