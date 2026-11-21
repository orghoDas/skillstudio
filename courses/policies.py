"""Course access policy — the ONE place that decides who may see what (CRS-01).

Three questions, each building on the previous one:

* ``can_view_course_catalog`` — may the user open the detail and outline?
  Published courses are public. Archived courses can also be opened by
  enrolled learners. Drafts and reviews are visible to managers.
* ``can_access_course_content`` — may the user study the course?  Requires
  catalog visibility first, then: free course, owner/admin, or an enrollment
  that grants access (active or completed; canceled does not).
* ``can_access_lesson`` — like content access, but a free-preview lesson of a
  visible course is open to everyone.

Lesson *progression* (locked until earlier lessons are done) is a separate
rule for enrolled students: ``enrollments.services.lesson_lock_state``.
"""

from django.db.models import Q

from accounts.utils import is_platform_admin
from courses.models import Course
from enrollments.constants import ACCESS_STATUSES
from enrollments.models import Enrollment


def can_manage_course(user, course):
    """Owner or platform admin."""
    return (
        getattr(user, 'is_authenticated', False)
        and (
            is_platform_admin(user)
            or course.instructor_id == getattr(user, 'id', None)
        )
    )


def has_access_enrollment(user, course):
    """True if the user owns the course (active or completed enrollment)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return Enrollment.objects.filter(
        user=user,
        course=course,
        status__in=ACCESS_STATUSES,
    ).exists()


def can_view_course_catalog(user, course):
    return (
        course.status == 'published' or can_manage_course(user, course)
        or (course.status == 'archived' and has_access_enrollment(user, course))
    )


def visible_catalog_courses(user):
    """Queryset form of can_view_course_catalog for filtering collections."""
    if is_platform_admin(user):
        return Course.objects.all()
    visible = Q(status='published')
    if getattr(user, 'is_authenticated', False):
        owned_enrollments = Enrollment.objects.filter(user=user, status__in=ACCESS_STATUSES)
        visible |= Q(instructor=user) | Q(status='archived', pk__in=owned_enrollments.values('course_id'))
    return Course.objects.filter(visible)


def can_access_course_content(user, course):
    if can_manage_course(user, course):
        return True
    if course.status == 'published':
        return course.is_free or has_access_enrollment(user, course)
    return course.status == 'archived' and has_access_enrollment(user, course)


def can_access_lesson(user, lesson):
    course = lesson.module.course
    if lesson.is_free:
        return can_view_course_catalog(user, course)
    return can_access_course_content(user, course)
