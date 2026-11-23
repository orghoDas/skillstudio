from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from enrollments.models import LessonProgress
from accounts.utils import is_platform_admin
from .models import Course, Module, Lesson
from .policies import can_manage_course
from .versions import copy_course_draft, record_published_version, snapshot_course


COURSE_TRANSITIONS = {
    'draft': {'under_review'},
    'under_review': {'published', 'draft'},
    'published': {'archived'},
    'archived': set(),
}


def _lock_course(course_id):
    return get_object_or_404(Course.objects.select_for_update(), pk=course_id)


def validate_course_for_submission(course: Course):
    modules = list(Module.objects.filter(course=course).annotate(
        has_lessons=Exists(Lesson.objects.filter(module_id=OuterRef('pk'))),
    ))
    if not modules:
        raise ValidationError("Course must have at least one module.")

    for module in modules:
        if not module.has_lessons:
            raise ValidationError(
                f"Module '{module.title}' has no lessons."
            )


    if not course.is_free and not Lesson.objects.filter(module__course=course, is_free=False).exists():
        raise ValidationError("A paid course needs at least one lesson that is not a free preview.")

    missing_quizzes = Lesson.objects.filter(module__course=course, content_type='quiz').exclude(
        quiz__is_published=True,
    )
    empty_quizzes = Lesson.objects.filter(
        module__course=course, content_type='quiz', quiz__questions__isnull=True,
    )
    if (missing_quizzes | empty_quizzes).exists():
        raise ValidationError("Publish a quiz with questions for each quiz lesson before submitting the course.")


@transaction.atomic
def transition(course, to_state, actor, reason=''):
    """Apply a review or archive action with ownership checked under a row lock."""
    course = _lock_course(course.pk)
    return _transition_locked(course, to_state, actor, reason=reason)


def _transition_locked(course, to_state, actor, *, reason='', edited=False):
    if not can_manage_course(actor, course):
        raise PermissionDenied("You do not have permission to manage this course.")
    if (to_state == 'published' or (to_state == 'draft' and not edited)) and not is_platform_admin(actor):
        raise PermissionDenied("Only a platform admin can review this course.")
    if to_state not in COURSE_TRANSITIONS[course.status]:
        raise ValidationError(f"A {course.get_status_display().lower()} course cannot move to {to_state.replace('_', ' ')}.")

    now = timezone.now()
    if to_state == 'under_review':
        validate_course_for_submission(course)
        updates = {'submitted_for_review_at': now, 'reviewed_by': None, 'reviewed_at': None, 'rejection_reason': ''}
    elif to_state == 'published':
        validate_course_for_submission(course)
        if course.revision_of_id:
            source = _lock_course(course.revision_of_id)
            course.revision_of = source
            if source.status == 'published':
                _transition_locked(source, 'archived', actor)
            elif source.status != 'archived':
                raise ValidationError("The previous version must be published or archived.")
        updates = {
            'reviewed_by': actor, 'reviewed_at': now, 'published_at': now,
            'rejection_reason': '', 'current_version': record_published_version(course),
        }
    elif to_state == 'archived':
        updates = {'archived_at': now}
        if not course.current_version_id:
            updates['current_version'] = record_published_version(course)
    elif edited:
        updates = {'submitted_for_review_at': None, 'reviewed_by': None, 'reviewed_at': None, 'rejection_reason': ''}
    else:
        if not reason:
            raise ValidationError("Rejection reason is required.")
        updates = {'reviewed_by': actor, 'reviewed_at': now, 'rejection_reason': reason}

    course.status = to_state
    for field, value in updates.items():
        setattr(course, field, value)
    course.save(update_fields=['status', 'updated_at', *updates])
    return course


def lock_course_for_edit(course, actor):
    """Acquire the lifecycle lock inside the caller's mutation transaction."""
    course = _lock_course(course.pk)
    if not can_manage_course(actor, course):
        raise PermissionDenied("You do not have permission to manage this course.")
    if course.status == 'under_review':
        return _transition_locked(course, 'draft', actor, edited=True)
    if not course.is_editable():
        raise ValidationError("Edit a draft revision to change a published or archived course.")
    return course


def lock_draft_for_deletion(course, actor):
    course = _lock_course(course.pk)
    if not can_manage_course(actor, course):
        raise PermissionDenied("You do not have permission to manage this course.")
    if not course.is_editable():
        raise ValidationError("Only draft courses can be deleted.")
    return course


@transaction.atomic
def start_new_version(course, actor):
    source = _lock_course(course.pk)
    if not can_manage_course(actor, source):
        raise PermissionDenied("You do not have permission to manage this course.")
    if source.status != 'published':
        raise ValidationError("Only published courses can have a new revision.")
    existing = Course.objects.filter(revision_of=source).first()
    if existing:
        return existing, False
    data = snapshot_course(source)
    if not source.current_version_id:
        source.current_version = record_published_version(source, data)
        source.save(update_fields=['current_version'])
    return copy_course_draft(source, data), True


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
