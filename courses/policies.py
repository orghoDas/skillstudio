from enrollments.models import Enrollment


def is_platform_admin(user):
    return (
        getattr(user, 'is_authenticated', False)
        and (
            getattr(user, 'is_staff', False)
            or getattr(user, 'is_superuser', False)
            or getattr(user, 'role', None) == 'admin'
        )
    )


def can_manage_course(user, course):
    return (
        getattr(user, 'is_authenticated', False)
        and (
            is_platform_admin(user)
            or course.instructor_id == getattr(user, 'id', None)
        )
    )


def can_view_course_catalog(user, course):
    return course.status == 'published' or can_manage_course(user, course)


def can_access_course_content(user, course):
    if course.is_free or can_manage_course(user, course):
        return True

    if not getattr(user, 'is_authenticated', False):
        return False

    return Enrollment.objects.filter(
        user=user,
        course=course,
        status='active',
    ).exists()


def can_access_lesson(user, lesson):
    course = lesson.module.course
    return lesson.is_free or can_access_course_content(user, course)
