"""Course access policy — the ONE place that decides who may see what (CRS-01).

Three questions, each building on the previous one:

* ``can_view_course_catalog`` — may the user see the course exists (detail,
  outline)?  Published courses: everyone. Anything else: owner/admin only.
* ``can_access_course_content`` — may the user study the course?  Requires
  catalog visibility first, then: free course, owner/admin, or an enrollment
  that grants access (active or completed; canceled does not).
* ``can_access_lesson`` — like content access, but a free-preview lesson of a
  visible course is open to everyone.

Lesson *progression* (locked until earlier lessons are done) is a separate
rule for enrolled students: ``enrollments.services.lesson_lock_state``.
"""

from accounts.utils import is_platform_admin
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


def can_view_course_catalog(user, course):
    return course.status == 'published' or can_manage_course(user, course)


def has_access_enrollment(user, course):
    """True if the user owns the course (active or completed enrollment)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    return Enrollment.objects.filter(
        user=user,
        course=course,
        status__in=ACCESS_STATUSES,
    ).exists()


def can_access_course_content(user, course):
    if not can_view_course_catalog(user, course):
        return False
    if course.is_free or can_manage_course(user, course):
        return True
    return has_access_enrollment(user, course)


def can_access_lesson(user, lesson):
    course = lesson.module.course
    if not can_view_course_catalog(user, course):
        return False
    return lesson.is_free or can_access_course_content(user, course)
