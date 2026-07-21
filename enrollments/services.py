from django.db import transaction
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


def get_required_lessons(course):
    return Lesson.objects.filter(
        module__course=course,
        is_free=False
    ).order_by('module__position', 'position')


def get_completed_required_lesson_ids(enrollment):
    return set(
        enrollment.lesson_progress.filter(
            is_completed=True,
            lesson__is_free=False,
            lesson__module__course=enrollment.course
        ).values_list('lesson_id', flat=True)
    )


def get_lesson_completion_stats(enrollment):
    required_lessons = get_required_lessons(enrollment.course)
    required_ids = set(required_lessons.values_list('id', flat=True))
    completed_required_ids = get_completed_required_lesson_ids(enrollment)
    completed_count = len(required_ids & completed_required_ids)
    total_count = len(required_ids)

    return {
        'total_lessons': total_count,
        'completed_lessons': completed_count,
        'completed_lesson_ids': sorted(required_ids & completed_required_ids),
        'progress_percentage': round((completed_count / total_count * 100), 2) if total_count else 0,
        'all_required_completed': total_count > 0 and completed_count == total_count,
    }


def assessment_requirements_met(enrollment):
    try:
        from assessments.services import is_lesson_assessment_completed
    except ImportError:
        return True

    for lesson in get_required_lessons(enrollment.course):
        if not is_lesson_assessment_completed(enrollment.user, lesson):
            return False

    return True


@transaction.atomic
def evaluate_and_complete_enrollment(enrollment_id):
    enrollment = Enrollment.objects.select_for_update().select_related(
        'user',
        'course'
    ).get(id=enrollment_id)

    stats = get_lesson_completion_stats(enrollment)
    if not stats['all_required_completed'] or not assessment_requirements_met(enrollment):
        return False

    if not enrollment.is_completed:
        enrollment.status = 'completed'
        enrollment.is_completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=[
            'status',
            'is_completed',
            'completed_at'
        ])

        issue_certificate(enrollment.user, enrollment.course)

    return True


def check_and_complete_course(enrollment):
    return evaluate_and_complete_enrollment(enrollment.id)


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
    lessons = get_required_lessons(enrollment.course)
    completed_ids = get_completed_required_lesson_ids(enrollment)

    for lesson in lessons:
        if lesson.id not in completed_ids:
            return lesson

    return None

def get_next_lesson(enrollment, current_lesson):
    lessons = get_required_lessons(enrollment.course)
    completed_ids = get_completed_required_lesson_ids(enrollment)

    lesson_list = list(lessons)
    try:
        current_index = lesson_list.index(current_lesson)
    except ValueError:
        return None

    # Look for next incomplete required lesson after current.
    for lesson in lesson_list[current_index + 1:]:
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
