from django.utils import timezone

from .models import QuizAttempt
from .services_scoring import calculate_quiz_score


def auto_submit_attempt(attempt):
    if attempt.completed_at:
        return attempt

    calculate_quiz_score(attempt)
    attempt.is_auto_submitted = True
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=[
        "is_auto_submitted",
        "completed_at"
    ])

    return attempt
