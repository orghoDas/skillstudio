from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError
from rest_framework.exceptions import PermissionDenied as ApiPermissionDenied

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


COURSE_LESSON_ORDER = ('module__position', 'module_id', 'position', 'id')


def _completion_lessons(queryset):
    non_preview = Lesson.objects.filter(module__course_id=OuterRef('module__course_id'), is_free=False)
    # Existing courses with only previews can be completed by finishing every lesson.
    return queryset.filter(
        Q(is_free=False) | ~Exists(non_preview)
    )


def required_lessons_for_courses(course_ids):
    lessons = Lesson.objects.filter(module__course_id__in=course_ids)
    return _completion_lessons(lessons).order_by(*COURSE_LESSON_ORDER)


def get_required_lessons(course):
    return required_lessons_for_courses([course.pk])


def _required_completion_rows(queryset, course_id):
    non_preview = Lesson.objects.filter(module__course_id=OuterRef('lesson__module__course_id'), is_free=False)
    return queryset.filter(is_completed=True, lesson__module__course_id=course_id).filter(
        Q(lesson__is_free=False) | ~Exists(non_preview)
    )


def with_enrollment_progress(queryset, *, completed_ids=False, durations=False):
    """Load progress without per-enrollment queries or fan-out across joins."""
    lessons = (
        _completion_lessons(Lesson.objects.filter(module__course_id=OuterRef('course_id')))
        .order_by()
        .values('module__course_id')
    )
    queryset = queryset.annotate(required_count=Coalesce(
        Subquery(lessons.annotate(total=Count('pk')).values('total')), 0,
    ))
    progress = LessonProgress.objects.filter(enrollment_id=OuterRef('pk')).order_by().values('enrollment_id')
    if completed_ids:
        completed = _required_completion_rows(LessonProgress.objects.all(), F('enrollment__course_id'))
        queryset = queryset.prefetch_related(Prefetch(
            'lesson_progress', queryset=completed.only('enrollment_id', 'lesson_id').order_by('lesson_id'),
            to_attr='completed_required_progress',
        ))
    else:
        completed = _required_completion_rows(progress, OuterRef('course_id'))
        queryset = queryset.annotate(required_completed_count=Coalesce(
            Subquery(completed.annotate(total=Count('pk')).values('total')), 0,
        ))
    if durations:
        queryset = queryset.annotate(
            total_duration_seconds=Coalesce(Subquery(lessons.annotate(total=Sum('duration_seconds')).values('total')), 0),
            watched_time_seconds=Coalesce(Subquery(progress.annotate(total=Sum('watch_time')).values('total')), 0),
        )
    return queryset


def lesson_progress_percentage(completed, total):
    return round((completed / total) * 100, 2) if total else 0


def get_completed_required_lesson_ids(enrollment):
    return set(
        _required_completion_rows(enrollment.lesson_progress.all(), enrollment.course_id).values_list('lesson_id', flat=True)
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
        'progress_percentage': lesson_progress_percentage(completed_count, total_count),
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

    if created:
        available = WATCH_PROGRESS_GRACE_SECONDS
    else:
        # Quantize endpoints rather than every interval so repeated samples
        # cannot accumulate rounding credit or lose a fraction on every tick.
        available = max(0, int(now.timestamp()) - int(progress.updated_at.timestamp()))
    next_watch_time = progress.watch_time + min(watch_time_delta, available)
    if lesson.duration_seconds > 0:
        next_watch_time = max(progress.watch_time, min(next_watch_time, lesson.duration_seconds))

    credited_seconds = max(0, next_watch_time - progress.watch_time)
    progress.watch_time = next_watch_time
    progress.updated_at = now
    progress.save(update_fields=["watch_time", "updated_at"])
    if credited_seconds > 0:
        record_learning_activity(enrollment.user_id, now, local_zone=local_zone, watch_seconds=credited_seconds)
    return progress, credited_seconds


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
    required = [lesson for lesson in lessons if not lesson.is_free] or lessons
    return next(
        (lesson for lesson in required if lesson.pk not in completed_ids and not locks[lesson.pk]),
        None,
    )


def ordered_course_lessons(course):
    """All lessons of a course in one deterministic study order."""
    return list(Lesson.objects.filter(module__course=course).select_related('module').order_by(*COURSE_LESSON_ORDER))


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


def require_unlocked_lesson(enrollment, lesson):
    if enrollment is not None and lesson_lock_state(enrollment).get(lesson.pk):
        raise ApiPermissionDenied('Complete the previous lessons first.', code='lesson_locked')


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
