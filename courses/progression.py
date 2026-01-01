from courses.models import Lesson
from enrollments.models import LessonProgress


def get_next_lesson(enrollment):
    course = enrollment.course

    lessons = Lesson.objects.filter(
        module__course=course
    ).order_by('module__position', 'position')

    completed_ids = set(
        LessonProgress.objects.filter(
            enrollment=enrollment,
            is_completed=True
        ).values_list('lesson_id', flat=True)
    )

    for lesson in lessons:
        # Skip free lessons in progression
        if lesson.is_free:
            continue

        # Return first non-free lesson that's not completed
        if lesson.id not in completed_ids:
            return lesson

    return None
