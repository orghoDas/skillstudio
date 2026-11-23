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
    # Sum of the questions' marks; kept in sync by assessments.signals (ASM-04).
    total_marks = models.PositiveIntegerField(default=0)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True)
    passing_percentage = models.PositiveIntegerField(default=50)
    # ASM-04: a new quiz is a draft until the instructor publishes it.
    is_published = models.BooleanField(default=False)
    # ASM-01: how many graded attempts a student gets; null = unlimited.
    # Passing once is enough; a student who passed can't start again.
    max_attempts = models.PositiveIntegerField(default=3, null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "quizzes"

    def __str__(self):
        return self.title or f"Quiz for {self.lesson}"

    def compute_total_marks(self):
        return self.questions.aggregate(total=models.Sum("marks"))["total"] or 0

    def refresh_total_marks(self):
        """Recalculate total_marks from the questions and store it."""
        self.total_marks = self.compute_total_marks()
        Quiz.objects.filter(pk=self.pk).update(total_marks=self.total_marks)
        return self.total_marks

    def has_time_limit(self):
        return bool(self.time_limit_minutes)

    def counts_for_completion(self):
        """Only a published quiz with questions can gate lesson completion (ASM-01)."""
        return self.is_published and self.questions.exists()


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    started_at = models.DateTimeField(default=timezone.now)
    retry_granted = models.BooleanField(default=False, db_default=False)
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
    attempt_number = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            # ASM-01: retakes are allowed (Quiz.max_attempts), numbered per user...
            models.UniqueConstraint(
                fields=["quiz", "user", "attempt_number"],
                name="uniq_quiz_attempt_number_per_user",
            ),
            # ...but a student can only have one attempt in progress at a time.
            models.UniqueConstraint(
                fields=["quiz", "user"],
                condition=models.Q(completed_at__isnull=True),
                name="uniq_open_quiz_attempt_per_user",
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

    def is_past_submission_deadline(self, grace_seconds=0):
        """True once the time limit (plus a small network grace) has passed (ASM-02)."""
        if not self.quiz.time_limit_minutes:
            return False
        elapsed = (timezone.now() - self.started_at).total_seconds()
        return elapsed > self.quiz.time_limit_minutes * 60 + grace_seconds

class QuizQuestion(models.Model):
    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions"
    )
    question_text = models.TextField()
    explanation = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
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
