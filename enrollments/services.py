from django.utils import timezone

from courses.models import Lesson
from enrollments.constants import LESSON_COMPLETION_THRESHOLD
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
    total_lessons = Lesson.objects.filter(module__course=enrollment.course).count()
    completed_lessons = enrollment.lesson_progress.filter(is_completed=True).count()

    if total_lessons > 0 and total_lessons == completed_lessons:
        if not enrollment.is_completed:
            enrollment.is_completed = True
            enrollment.completed_at = timezone.now()
            enrollment.status = 'completed'
            enrollment.save(update_fields=['is_completed', 'completed_at', 'status'])
        return True

    return False


def auto_complete_lesson(progress):
    lesson_duration = progress.lesson.video_durattion

    if lesson_duration == 0:
        return False
    
    watched_ratio = progress.watch_time_seconds / lesson_duration
    return watched_ratio >= LESSON_COMPLETION_THRESHOLD


def get_previous_lesson(lesson):
    pre_lesson = Lesson.objects.filter(
        module=lesson.module,
        position__lt=lesson.position
    ).order_by('-position').first()

    if pre_lesson:
        return pre_lesson
    
    pre_module = lesson.module.course.modules.filter(
        position__lt=lesson.module.position
    ).order_by('-position').first()

    if not pre_module:
        return None
    
    return pre_module.lessons.order_by('-position').first()