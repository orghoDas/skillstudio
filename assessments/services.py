from decimal import Decimal
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from .models import (
    Quiz,
    QuizAttempt,
)


# ======================================================
# QUIZ SERVICES
# ======================================================

def build_quiz_attempt_snapshot(quiz: Quiz) -> list[dict]:
    """
    Capture the quiz evidence that this attempt will be graded against.
    """
    questions = quiz.questions.prefetch_related("options").order_by("id")
    return [
        {
            "question_id": question.id,
            "question_text": question.question_text,
            "difficulty": question.difficulty,
            "marks": question.marks,
            "options": [
                {
                    "option_id": option.id,
                    "option_text": option.option_text,
                    "is_correct": option.is_correct,
                }
                for option in question.options.all().order_by("id")
            ],
        }
        for question in questions
    ]


def get_snapshot_total_marks(question_snapshot: list[dict]) -> int:
    return sum(int(question.get("marks") or 0) for question in question_snapshot)


def ensure_attempt_snapshot(attempt: QuizAttempt) -> QuizAttempt:
    """
    Backfill older attempts so all grading paths use stable attempt evidence.
    """
    update_fields = []

    if not attempt.question_snapshot:
        attempt.question_snapshot = build_quiz_attempt_snapshot(attempt.quiz)
        update_fields.append("question_snapshot")

    if not attempt.total_marks_snapshot:
        attempt.total_marks_snapshot = get_snapshot_total_marks(attempt.question_snapshot)
        update_fields.append("total_marks_snapshot")

    if update_fields:
        attempt.save(update_fields=update_fields)

    return attempt


def _snapshot_question_by_id(attempt: QuizAttempt) -> dict[str, dict]:
    ensure_attempt_snapshot(attempt)
    return {
        str(question.get("question_id")): question
        for question in attempt.question_snapshot
    }


def validate_quiz_answer(
    attempt: QuizAttempt,
    question_id,
    option_id,
) -> tuple[str, str]:
    """
    Validate and normalize an answer against the attempt's frozen quiz evidence.
    """
    normalized_question_id = str(question_id)
    normalized_option_id = str(option_id)
    question = _snapshot_question_by_id(attempt).get(normalized_question_id)

    if question is None:
        raise ValidationError("Question is not part of this quiz attempt.")

    valid_option_ids = {
        str(option.get("option_id"))
        for option in question.get("options", [])
    }
    if normalized_option_id not in valid_option_ids:
        raise ValidationError("Option is not valid for this question.")

    return normalized_question_id, normalized_option_id


def normalize_quiz_answers(attempt: QuizAttempt, answers: dict) -> dict[str, str]:
    if not isinstance(answers, dict):
        raise ValidationError("Answers must be an object keyed by question id.")

    normalized_answers = {}
    for question_id, option_id in answers.items():
        normalized_question_id, normalized_option_id = validate_quiz_answer(
            attempt,
            question_id,
            option_id,
        )
        normalized_answers[normalized_question_id] = normalized_option_id

    return normalized_answers


@transaction.atomic
def save_quiz_answer(attempt: QuizAttempt, question_id, option_id) -> QuizAttempt:
    locked_attempt = (
        QuizAttempt.objects
        .select_for_update()
        .select_related("quiz")
        .get(pk=attempt.pk)
    )

    if locked_attempt.completed_at:
        raise ValidationError("Attempt already completed.")
    if locked_attempt.is_past_submission_deadline(QUIZ_SUBMIT_GRACE_SECONDS):
        raise ValidationError("Time is up for this attempt.")

    normalized_question_id, normalized_option_id = validate_quiz_answer(
        locked_attempt,
        question_id,
        option_id,
    )
    answers = dict(locked_attempt.answers or {})
    answers[normalized_question_id] = normalized_option_id
    locked_attempt.answers = answers
    locked_attempt.save(update_fields=["answers"])
    return locked_attempt


# Network latency allowance between the client timer hitting zero and the
# submission reaching the server (ASM-02). Answers arriving later are ignored.
QUIZ_SUBMIT_GRACE_SECONDS = 10


def _next_attempt_number(quiz, user) -> int:
    last = (
        QuizAttempt.objects.filter(quiz=quiz, user=user)
        .order_by("-attempt_number")
        .values_list("attempt_number", flat=True)
        .first()
    )
    return (last or 0) + 1


def get_quiz_attempt_status(user, quiz: Quiz) -> dict:
    """What a student may do next with a quiz (used by the quiz detail API)."""
    attempts = QuizAttempt.objects.filter(quiz=quiz, user=user)
    completed = attempts.filter(completed_at__isnull=False)
    used = completed.count()
    last = completed.order_by("-attempt_number").first()
    has_passed = completed.filter(passed=True).exists()
    remaining = None if quiz.max_attempts is None else max(0, quiz.max_attempts - used)
    return {
        "attempts_used": used,
        "max_attempts": quiz.max_attempts,
        "attempts_remaining": remaining,
        "has_passed": has_passed,
        "has_open_attempt": attempts.filter(completed_at__isnull=True).exists(),
        "can_start": not has_passed and (remaining is None or remaining > 0),
        "last_attempt": (
            {"attempt_number": last.attempt_number, "score": last.score, "passed": last.passed,
             "is_auto_submitted": last.is_auto_submitted}
            if last else None
        ),
    }


def start_quiz_attempt(user, quiz: Quiz) -> QuizAttempt:
    """Start (or resume) an attempt.

    ASM-01: retakes are allowed up to ``quiz.max_attempts`` (null = unlimited).
    An open attempt is resumed; one whose time ran out is first graded from its
    saved answers. Starting again after passing is refused.
    """
    with transaction.atomic():
        locked_quiz = Quiz.objects.select_for_update().get(pk=quiz.pk)
        if not locked_quiz.is_published:
            raise PermissionDenied("Quiz is not published.")

        open_attempt = (
            QuizAttempt.objects.select_for_update()
            .filter(quiz=locked_quiz, user=user, completed_at__isnull=True)
            .first()
        )
        if open_attempt:
            if not open_attempt.is_past_submission_deadline(QUIZ_SUBMIT_GRACE_SECONDS):
                return ensure_attempt_snapshot(open_attempt)
            submit_quiz_attempt(open_attempt, None, auto_submitted=True)

        status = get_quiz_attempt_status(user, locked_quiz)
        if status["has_passed"]:
            raise ValidationError("You have already passed this quiz.")
        if not status["can_start"]:
            raise ValidationError("You have no attempts left for this quiz.")

        question_snapshot = build_quiz_attempt_snapshot(locked_quiz)
        try:
            with transaction.atomic():
                return QuizAttempt.objects.create(
                    quiz=locked_quiz,
                    user=user,
                    attempt_number=_next_attempt_number(locked_quiz, user),
                    started_at=timezone.now(),
                    question_snapshot=question_snapshot,
                    total_marks_snapshot=get_snapshot_total_marks(question_snapshot),
                )
        except IntegrityError:
            # A concurrent request created the open attempt first: resume it.
            attempt = QuizAttempt.objects.select_for_update().get(
                quiz=locked_quiz, user=user, completed_at__isnull=True
            )
            return ensure_attempt_snapshot(attempt)


@transaction.atomic
def submit_quiz_attempt(attempt: QuizAttempt, answers: dict | None = None, auto_submitted: bool = False) -> QuizAttempt:
    """
    Submit quiz answers and auto-grade.
    answers = {question_id: option_id}

    ASM-02: if the time limit (plus a short network grace) has passed, the
    posted ``answers`` are ignored and only answers saved in time (via the
    per-answer endpoint) are graded; the attempt is marked auto-submitted.
    """
    attempt = (
        QuizAttempt.objects
        .select_for_update()
        .select_related("quiz")
        .get(pk=attempt.pk)
    )

    if attempt.completed_at:
        raise ValidationError("Quiz already submitted.")

    quiz = attempt.quiz
    if attempt.is_past_submission_deadline(QUIZ_SUBMIT_GRACE_SECONDS):
        answers = None
        auto_submitted = True
    if answers is None:
        answers = attempt.answers or {}

    ensure_attempt_snapshot(attempt)
    normalized_answers = normalize_quiz_answers(attempt, answers)

    total_marks = Decimal("0.0")
    earned_marks = Decimal("0.0")

    for question in attempt.question_snapshot:
        question_marks = Decimal(str(question.get("marks") or 0))
        total_marks += question_marks

        selected_option_id = normalized_answers.get(str(question.get("question_id")))
        if not selected_option_id:
            continue

        correct_option_ids = {
            str(option.get("option_id"))
            for option in question.get("options", [])
            if option.get("is_correct")
        }
        if selected_option_id in correct_option_ids:
            earned_marks += question_marks

    percentage = (earned_marks / total_marks) * 100 if total_marks > 0 else 0

    attempt.answers = normalized_answers
    attempt.score = earned_marks
    attempt.passed = percentage >= quiz.passing_percentage
    attempt.completed_at = timezone.now()
    attempt.is_auto_submitted = auto_submitted

    attempt.save(update_fields=[
        "answers",
        "question_snapshot",
        "total_marks_snapshot",
        "score",
        "passed",
        "completed_at",
        "is_auto_submitted",
    ])

    return attempt


def is_quiz_passed(user, quiz: Quiz) -> bool:
    """Passing any attempt is enough."""
    return QuizAttempt.objects.filter(
        quiz=quiz,
        user=user,
        passed=True
    ).exists()

# ======================================================
# LESSON COMPLETION CHECK
# ======================================================

def is_lesson_assessment_completed(user, lesson) -> bool:
    """
    Determines whether lesson assessment requirements are satisfied.

    ASM-01: an unpublished quiz (which students can't even start) or a quiz
    with no questions never blocks completion.
    """
    quiz = Quiz.objects.filter(lesson=lesson).first()
    if quiz is None or not quiz.counts_for_completion():
        return True
    return is_quiz_passed(user, quiz)
