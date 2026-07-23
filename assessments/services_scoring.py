from .services import submit_quiz_attempt


def calculate_quiz_score(attempt):
    attempt = submit_quiz_attempt(attempt)
    return attempt.score
