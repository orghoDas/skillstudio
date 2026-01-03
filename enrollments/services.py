from django.utils import timezone
from django.core.exceptions import PermissionDenied

from certificates.services import issue_certificate
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

def check_and_complete_course(enrollment):
    total_lessons = Lesson.objects.filter(
        module__course=enrollment.course,
        is_free=False
    ).count()

    completed_lessons = enrollment.lesson_progress.filter(
        is_completed=True
    ).count()

    if total_lessons == 0:
        return False

    if completed_lessons >= total_lessons:
        if not enrollment.is_completed:
            enrollment.status = 'completed'
            enrollment.is_completed = True
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=[
                'status',
                'is_completed',
                'completed_at'
            ])

            # 🎓 Issue certificate automatically
            issue_certificate(enrollment.user, enrollment.course)

        return True

    return False


def auto_complete_lesson(progress):
    lesson_duration = progress.lesson.duration_seconds

    if lesson_duration == 0:
        return False
    
    watched_ratio = progress.watch_time / lesson_duration
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

def get_resume_lesson(enrollment):
    lessons = Lesson.objects.filter(
        module__course=enrollment.course,
        is_free=False
    ).order_by('module__position', 'position')

    completed_ids = set(
        LessonProgress.objects.filter(
            enrollment=enrollment,
            is_completed=True
        ).values_list('lesson_id', flat=True)
    )

    for lesson in lessons:
        if lesson.id not in completed_ids:
            return lesson

    return None

def get_next_lesson(enrollment, current_lesson):
    lessons = Lesson.objects.filter(
        module__course=enrollment.course
    ).order_by('module__position', 'position')

    completed_ids = set(
        LessonProgress.objects.filter(
            enrollment=enrollment,
            is_completed=True
        ).values_list('lesson_id', flat=True)
    )

    lesson_list = list(lessons)
    try:
        current_index = lesson_list.index(current_lesson)
    except ValueError:
        return None

    # Look for next incomplete lesson after current
    for lesson in lesson_list[current_index + 1:]:
        # Skip free lessons in progression
        if lesson.is_free:
            continue

        # Return first non-free lesson that's not completed
        if lesson.id not in completed_ids:
            return lesson

    return None


def require_active_enrollment(user, course):
    """Validate that user has active enrollment for course."""
    if user.is_staff or user.is_superuser:
        return None

    if course.instructor == user:
        return None

    enrollment = Enrollment.objects.filter(
        user=user,
        course=course,
        status='active'
    ).first()

    if not enrollment:
        raise PermissionDenied("Active enrollment required.")

    return enrollment