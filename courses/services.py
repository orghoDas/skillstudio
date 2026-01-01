from django.core.exceptions import ValidationError

from enrollments.models import LessonProgress
from .models import Course, Module, Lesson


def validate_course_for_submission(course: Course):
    modules = Module.objects.filter(course=course)

    if not modules.exists():
        raise ValidationError("Course must have at least one module.")

    for module in modules:
        if not Lesson.objects.filter(module=module).exists():
            raise ValidationError(
                f"Module '{module.title}' has no lessons."
            )

def is_course_completed(enrollment):
    """
    Server-side source of truth for course completion.
    """

    lessons = Lesson.objects.filter(
        module__course=enrollment.course,
        is_free=False
    )

    total_required = lessons.count()

    completed = LessonProgress.objects.filter(
        enrollment=enrollment,
        lesson__in=lessons,
        is_completed=True
    ).count()

    return total_required > 0 and completed == total_required