from django.utils import timezone
from .models import Enrollment, LessonProgress


def mark_lesson_completed(enrollment, lesson):
    progress, _ = LessonProgress.objects.get_or_create(
        enrollment=enrollment,
        user=enrollment.user,
        lesson=lesson
    )

    if not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.save()

    return progress


def check_and_mark_course_completed(enrollment):
    total_lessons = enrollment.course.lessons.count()
    completed_lessons = enrollment.lesson_progress.filter(is_completed=True).count()

    if total_lessons > 0 and total_lessons == completed_lessons:
        enrollment.is_completed = True
        enrollment.completed_at = timezone.now()
        enrollment.status = 'completed'
        enrollment.save()
        return True

    return False