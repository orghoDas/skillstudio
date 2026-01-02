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

    def has_time_limit(self):
        return bool(self.time_limit_minutes)


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
