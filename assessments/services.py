from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from .models import (
    Quiz,
    QuizAttempt,
    QuizQuestion,
    QuestionOption,
    Assignment,
    Submission,
)


# ======================================================
# QUIZ SERVICES
# ======================================================

def start_quiz_attempt(user, quiz: Quiz) -> QuizAttempt:
    """
    Starts a quiz attempt (1 per user per quiz).
    """
    if not quiz.is_published:
        raise PermissionDenied("Quiz is not published.")

    attempt, created = QuizAttempt.objects.get_or_create(
        quiz=quiz,
        user=user,
        defaults={"started_at": timezone.now()}
    )

    if not created and attempt.completed_at:
        raise ValidationError("Quiz already completed.")

    return attempt


@transaction.atomic
def submit_quiz_attempt(attempt: QuizAttempt, answers: dict) -> QuizAttempt:
    """
    Submit quiz answers and auto-grade.
    answers = {question_id: option_id}
    """

    if attempt.completed_at:
        raise ValidationError("Quiz already submitted.")

    quiz = attempt.quiz
    questions = quiz.questions.prefetch_related("options")

    total_marks = Decimal("0.0")
    earned_marks = Decimal("0.0")

    for question in questions:
        total_marks += question.marks

        selected_option_id = answers.get(str(question.id))
        if not selected_option_id:
            continue

        try:
            option = question.options.get(id=selected_option_id)
        except QuestionOption.DoesNotExist:
            continue

        if option.is_correct:
            earned_marks += question.marks

    percentage = (earned_marks / total_marks) * 100 if total_marks > 0 else 0

    attempt.answers = answers
    attempt.score = earned_marks
    attempt.passed = percentage >= quiz.passing_percentage
    attempt.completed_at = timezone.now()

    attempt.save(update_fields=[
        "answers",
        "score",
        "passed",
        "completed_at"
    ])

    return attempt


def is_quiz_passed(user, quiz: Quiz) -> bool:
    return QuizAttempt.objects.filter(
        quiz=quiz,
        user=user,
        passed=True
    ).exists()


# ======================================================
# ASSIGNMENT SERVICES
# ======================================================

def submit_assignment(
    user,
    assignment: Assignment,
    *,
    file_url: str = None,
    text: str = None
) -> Submission:
    """
    Submit or resubmit assignment.
    """

    if assignment.due_date and timezone.now() > assignment.due_date:
        raise ValidationError("Assignment submission deadline passed.")

    submission, _ = Submission.objects.update_or_create(
        assignment=assignment,
        user=user,
        defaults={
            "file_url": file_url,
            "text": text,
            "submitted_at": timezone.now()
        }
    )

    return submission


def grade_submission(
    submission: Submission,
    *,
    grade: Decimal,
    feedback: str,
    grader
) -> Submission:
    """
    Instructor grading.
    """

    if grade < 0 or grade > submission.assignment.max_score:
        raise ValidationError("Invalid grade value.")

    submission.grade = grade
    submission.feedback = feedback
    submission.graded_by = grader
    submission.graded_at = timezone.now()

    submission.save(update_fields=[
        "grade",
        "feedback",
        "graded_by",
        "graded_at"
    ])

    return submission


def is_assignment_passed(submission: Submission) -> bool:
    """
    Simple pass logic (>= 50%).
    """
    if submission.grade is None:
        return False

    passing_score = submission.assignment.max_score * Decimal("0.5")
    return submission.grade >= passing_score


# ======================================================
# LESSON COMPLETION CHECK
# ======================================================

def is_lesson_assessment_completed(user, lesson) -> bool:
    """
    Determines whether lesson assessment requirements are satisfied.
    """

    # Quiz logic
    if hasattr(lesson, "quiz"):
        if not is_quiz_passed(user, lesson.quiz):
            return False

    # Assignment logic
    if hasattr(lesson, "assignment"):
        submission = Submission.objects.filter(
            assignment=lesson.assignment,
            user=user,
            grade__isnull=False
        ).first()

        if not submission or not is_assignment_passed(submission):
            return False

    return True


# ======================================================
# COURSE VALIDATION HOOK
# ======================================================

def validate_course_completion(user, course) -> bool:
    """
    Ensures all lessons with assessments are completed.
    """

    lessons = course.modules.prefetch_related(
        "lessons__quiz",
        "lessons__assignment"
    ).values_list("lessons", flat=True)

    for lesson in lessons:
        if not is_lesson_assessment_completed(user, lesson):
            return False

    return True
