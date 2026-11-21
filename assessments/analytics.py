from django.db.models import Avg, Count, Q
from .models import (
    Quiz,
    QuizAttempt,
    QuizQuestion,
)


def graded_attempts():
    """Finished attempts only: an in-progress attempt has no score yet (ASM-04)."""
    return QuizAttempt.objects.filter(completed_at__isnull=False)


def get_course_assessment_overview(course):
    quizzes = Quiz.objects.filter(lesson__module__course=course)

    quiz_stats = (
        graded_attempts()
        .filter(quiz__in=quizzes)
        .values("quiz_id", "quiz__title")
        .annotate(
            attempts=Count("id"),
            avg_score=Avg("score"),
            pass_count=Count("id", filter=Q(passed=True)),
        )
    )

    return {
        "quiz_overview": quiz_stats,
    }


def get_quiz_question_analytics(quiz):
    questions = QuizQuestion.objects.filter(quiz=quiz).prefetch_related("options")
    attempts = list(graded_attempts().filter(quiz=quiz).only("answers"))

    analytics = []

    for q in questions:
        question_key = str(q.id)
        correct_option_ids = {
            str(option.id)
            for option in q.options.all()
            if option.is_correct
        }
        answered_values = [
            str(attempt.answers[question_key])
            for attempt in attempts
            if question_key in attempt.answers
        ]

        total = len(answered_values)
        wrong = sum(
            1
            for selected_option_id in answered_values
            if selected_option_id not in correct_option_ids
        )

        analytics.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "attempts": total,
            "wrong_attempts": wrong,
            "wrong_ratio": round(wrong / total, 2) if total else 0
        })

    return analytics
