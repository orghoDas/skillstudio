from django.db import IntegrityError, transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError

from certificates.services import issue_certificate
from accounts.utils import is_platform_admin
from courses.models import Lesson
from enrollments.constants import LESSON_COMPLETION_THRESHOLD
from enrollments.constants import ACCESS_STATUSES
from .models import Enrollment, LessonProgress

MAX_WATCH_PROGRESS_DELTA_SECONDS = 120
WATCH_PROGRESS_GRACE_SECONDS = 15


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


@transaction.atomic
def update_lesson_watch_progress(enrollment, lesson, watch_time_delta):
    """
    Apply one bounded incremental watch-progress event.

    Clients may not set absolute watch time. They can only report a plausible
    delta since the last accepted progress event.
    """
    if watch_time_delta < 0:
        raise ValidationError("Watch time delta cannot be negative.")
    if watch_time_delta > MAX_WATCH_PROGRESS_DELTA_SECONDS:
        raise ValidationError(
            f"Watch time delta cannot exceed {MAX_WATCH_PROGRESS_DELTA_SECONDS} seconds."
        )

    enrollment = Enrollment.objects.select_for_update().get(pk=enrollment.pk)
    now = timezone.now()

    try:
        progress = LessonProgress.objects.select_for_update().get(
            enrollment=enrollment,
            user=enrollment.user,
            lesson=lesson,
        )
        created = False
    except LessonProgress.DoesNotExist:
        try:
            progress = LessonProgress.objects.create(
                enrollment=enrollment,
                user=enrollment.user,
                lesson=lesson,
            )
            created = True
        except IntegrityError:
            progress = LessonProgress.objects.select_for_update().get(
                enrollment=enrollment,
                user=enrollment.user,
                lesson=lesson,
            )
            created = False

    if not created:
        elapsed_seconds = max(0, int((now - progress.updated_at).total_seconds()))
        plausible_delta = min(
            MAX_WATCH_PROGRESS_DELTA_SECONDS,
            elapsed_seconds + WATCH_PROGRESS_GRACE_SECONDS,
        )
        if watch_time_delta > plausible_delta:
            raise ValidationError(
                f"Watch time delta is too large for elapsed playback time; maximum allowed is {plausible_delta} seconds."
            )

    max_duration = lesson.duration_seconds
    next_watch_time = progress.watch_time + watch_time_delta
    if max_duration > 0:
        next_watch_time = min(next_watch_time, max_duration)

    progress.watch_time = next_watch_time
    progress.updated_at = now
    progress.save(update_fields=["watch_time", "updated_at"])
    return progress


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


def ordered_course_lessons(course):
    """All lessons of a course in one deterministic study order."""
    return list(
        Lesson.objects.filter(module__course=course)
        .select_related('module')
        .order_by('module__position', 'module__id', 'position', 'id')
    )


def completed_lesson_ids(enrollment):
    if enrollment is None:
        return set()
    return set(
        enrollment.lesson_progress.filter(is_completed=True).values_list('lesson_id', flat=True)
    )


def lesson_lock_state(enrollment, lessons=None, completed_ids=None):
    """The single progression rule (ENR-03): ``{lesson_id: is_locked}``.

    * Free lessons are never locked and never gate later lessons.
    * A required lesson is unlocked iff every earlier required lesson in study
      order is completed (so exactly the first incomplete one is open).
    * Without an enrollment (owner, admin, free-course visitor) nothing is locked.
    """
    if lessons is None:
        lessons = ordered_course_lessons(enrollment.course) if enrollment else []
    if enrollment is None:
        return {lesson.id: False for lesson in lessons}
    if completed_ids is None:
        completed_ids = completed_lesson_ids(enrollment)

    state, gate_open = {}, True
    for lesson in lessons:
        if lesson.is_free:
            state[lesson.id] = False
            continue
        state[lesson.id] = not gate_open
        if lesson.id not in completed_ids:
            gate_open = False
    return state


def get_access_enrollment(user, course):
    """The user's enrollment that grants access (active or completed), or None."""
    if not getattr(user, 'is_authenticated', False):
        return None
    return Enrollment.objects.filter(user=user, course=course, status__in=ACCESS_STATUSES).first()


def require_active_enrollment(user, course):
    """Validate that user has active enrollment for course."""
    if is_platform_admin(user):
        return None

    if course.instructor == user:
        return None

    enrollment = Enrollment.objects.filter(
        user=user,
        course=course,
        status__in=ACCESS_STATUSES
    ).first()

    if not enrollment:
        raise PermissionDenied("Active enrollment required.")

    return enrollment
