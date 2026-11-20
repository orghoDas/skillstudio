from .models import QuizAttempt
from .services import submit_quiz_attempt


def auto_submit_attempt(attempt):
    """Grade an attempt whose time ran out from its saved answers (ASM-02).

    Uses the single grading path (submit_quiz_attempt), which marks the
    attempt as auto-submitted and ignores anything posted after the deadline.
    """
    if attempt.completed_at:
        return attempt
    return submit_quiz_attempt(attempt, None, auto_submitted=True)
