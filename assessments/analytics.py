from django.db.models import Avg, Count, Q
from .models import (
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Assignment,
    Submission
)


def get_course_assessment_overview(course):
    quizzes = Quiz.objects.filter(lesson__module__course=course)

    quiz_stats = (
        QuizAttempt.objects
        .filter(quiz__in=quizzes)
        .values("quiz_id", "quiz__title")
        .annotate(
            attempts=Count("id"),
            avg_score=Avg("score"),
            pass_count=Count("id", filter=Q(passed=True)),
        )
    )

    assignments = Assignment.objects.filter(
        lesson__module__course=course
    )

    assignment_stats = (
        Submission.objects
        .filter(assignment__in=assignments)
        .values("assignment_id", "assignment__title")
        .annotate(
            submissions=Count("id"),
            graded=Count("id", filter=Q(grade__isnull=False)),
            avg_grade=Avg("grade"),
        )
    )

    return {
        "quiz_overview": quiz_stats,
        "assignment_overview": assignment_stats
    }


def get_quiz_question_analytics(quiz):
    questions = QuizQuestion.objects.filter(quiz=quiz)

    analytics = []

    for q in questions:
        total = QuizAttempt.objects.filter(
            quiz=quiz,
            answers__has_key=str(q.id)
        ).count()

        wrong = QuizAttempt.objects.filter(
            quiz=quiz
        ).exclude(
            answers__contains={str(q.id): q.correct_answer}
        ).count()

        analytics.append({
            "question_id": q.id,
            "question_text": q.question_text,
            "attempts": total,
            "wrong_attempts": wrong,
            "wrong_ratio": round(wrong / total, 2) if total else 0
        })

    return analytics
