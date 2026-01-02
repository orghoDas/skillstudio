from decimal import Decimal
from django.utils import timezone

from .models import QuizAttempt, QuestionOption


def calculate_quiz_score(attempt):
    total = Decimal("0")

    for question_id, selected_option_id in attempt.answers.items():
        option = QuestionOption.objects.filter(
            id=selected_option_id,
            is_correct=True
        ).first()

        if option:
            total += Decimal("1")

    attempt.score = total
    attempt.completed_at = timezone.now()
    attempt.save(update_fields=["score", "completed_at"])

    return total
