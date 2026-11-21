from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError

from certificates.services import issue_certificate
from certificates.models import Certificate
from accounts.utils import is_platform_admin
from courses.models import Lesson
from enrollments.constants import LESSON_COMPLETION_THRESHOLD
from enrollments.constants import ACCESS_STATUSES
from students.activity import record_learning_activity
from .models import Enrollment, LessonProgress

MAX_WATCH_PROGRESS_DELTA_SECONDS = 120
WATCH_PROGRESS_GRACE_SECONDS = 15


@transaction.atomic
def mark_lesson_completed(enrollment, lesson, *, local_zone=None, record_activity=True):
    progress, _ = LessonProgress.objects.select_for_update().get_or_create(
        enrollment=enrollment,
        user=enrollment.user,
        lesson=lesson
    )

    if not progress.is_completed:
        progress.is_completed = True
        progress.completed_at = timezone.now()
        progress.save(update_fields=['is_completed', 'completed_at', 'updated_at'])
        if record_activity:
            record_learning_activity(enrollment.user_id, progress.completed_at, local_zone=local_zone)

    return progress


def _course_lessons_in_order(course):
    return Lesson.objects.filter(module__course=course).order_by(
        'module__position', 'module_id', 'position', 'id',
    )


def get_required_lessons(course):
    return _course_lessons_in_order(course).filter(is_free=False)


def get_completed_required_lesson_ids(enrollment):
    return set(
        enrollment.lesson_progress.filter(
            is_completed=True,
            lesson__is_free=False,
            lesson__module__course=enrollment.course
        ).values_list('lesson_id', flat=True)
    )


def get_lesson_completion_stats(enrollment, *, required_lessons=None):
    if required_lessons is None:
        required_ids = set(get_required_lessons(enrollment.course).values_list('id', flat=True))
    else:
        required_ids = {lesson.pk for lesson in required_lessons}
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
    from exams.services import course_exam_requirements_met

    enrollment = Enrollment.objects.select_for_update().select_related(
        'user',
        'course'
    ).get(id=enrollment_id)

    if enrollment.status not in ACCESS_STATUSES:
        return False

    has_certificate = Certificate.objects.filter(
        user_id=enrollment.user_id, course_id=enrollment.course_id, revoked_at__isnull=True,
    ).exists()
    if enrollment.status == 'completed' and enrollment.is_completed and has_certificate:
        return True

    stats = get_lesson_completion_stats(enrollment)
    if (
        not stats['all_required_completed']
        or not assessment_requirements_met(enrollment)
        or not course_exam_requirements_met(enrollment.user, enrollment.course)
    ):
        return False

    if enrollment.status != 'completed' or not enrollment.is_completed or enrollment.completed_at is None:
        enrollment.status = 'completed'
        enrollment.is_completed = True
        enrollment.completed_at = enrollment.completed_at or timezone.now()
        enrollment.save(update_fields=[
            'status',
            'is_completed',
            'completed_at'
        ])

    issue_certificate(enrollment.user, enrollment.course)

    return True


@transaction.atomic
def cancel_enrollments(queryset):
    """Cancel access and revoke certificates in the same transaction."""
    enrollments = list(queryset.filter(status__in=ACCESS_STATUSES).order_by('pk').select_for_update(of=('self',)))
    revoked_at = timezone.now()
    for enrollment in enrollments:
        Certificate.objects.filter(
            user_id=enrollment.user_id, course_id=enrollment.course_id, revoked_at__isnull=True,
        ).update(revoked_at=revoked_at)
    return Enrollment.objects.filter(pk__in=[enrollment.pk for enrollment in enrollments]).update(status='canceled')


def check_and_complete_course(enrollment):
    return evaluate_and_complete_enrollment(enrollment.id)


def auto_complete_lesson(progress):
    lesson_duration = progress.lesson.duration_seconds

    if lesson_duration == 0:
        return False
    
    watched_ratio = progress.watch_time / lesson_duration
    return watched_ratio >= LESSON_COMPLETION_THRESHOLD


@transaction.atomic
def update_lesson_watch_progress(enrollment, lesson, watch_time_delta, *, local_zone=None):
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

    progress, created = LessonProgress.objects.select_for_update().get_or_create(
        enrollment=enrollment,
        user_id=enrollment.user_id,
        lesson=lesson,
    )

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

    credited_seconds = max(0, next_watch_time - progress.watch_time)
    progress.watch_time = next_watch_time
    progress.updated_at = now
    progress.save(update_fields=["watch_time", "updated_at"])
    if watch_time_delta > 0:
        record_learning_activity(enrollment.user_id, now, local_zone=local_zone, watch_seconds=credited_seconds)
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

def get_resume_lesson(enrollment, *, lessons=None, completed_ids=None):
    """Find the first unlocked, incomplete required lesson in study order."""
    if lessons is None:
        lessons = ordered_course_lessons(enrollment.course)
    if completed_ids is None:
        completed_ids = completed_lesson_ids(enrollment)
    locks = lesson_lock_state(enrollment, lessons, completed_ids)
    return next(
        (lesson for lesson in lessons
         if not lesson.is_free and lesson.pk not in completed_ids and not locks[lesson.pk]),
        None,
    )


def ordered_course_lessons(course):
    """All lessons of a course in one deterministic study order."""
    return list(_course_lessons_in_order(course).select_related('module'))


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
