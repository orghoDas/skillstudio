from django.utils import timezone
from decimal import Decimal

from .models import Submission, Rubric
from enrollments.services import check_and_complete_course


def grade_submission(submission, score, feedback=""):
    submission.grade = Decimal(score)
    submission.feedback = feedback
    submission.graded_at = timezone.now()
    submission.save(update_fields=["grade", "feedback", "graded_at"])

    enrollment = submission.assignment.lesson.module.course.enrollments.filter(
        user=submission.user
    ).first()

    if enrollment:
        check_and_complete_course(enrollment)

    return submission


def grade_submission_with_rubric(submission, rubric_scores, feedback=""):
    rubric = submission.assignment.rubric
    total = Decimal("0")

    for item in rubric.criteria:
        key = item["key"]
        max_score = Decimal(str(item["max"]))
        value = Decimal(str(rubric_scores.get(key, 0)))

        if value > max_score:
            raise ValueError(f"{key} exceeds max score")

        total += value

    if total > rubric.total_marks:
        raise ValueError("Total rubric score exceeds assignment total")

    submission.grade = total
    submission.feedback = feedback
    submission.graded_at = timezone.now()
    submission.save(update_fields=["grade", "feedback", "graded_at"])

    enrollment = submission.assignment.lesson.module.course.enrollments.filter(
        user=submission.user
    ).first()

    if enrollment:
        check_and_complete_course(enrollment)

    return submission
