from django.utils import timezone
from courses.models import Lesson
from .models import Enrollment, LessonProgress
from django.core.exceptions import PermissionDenied 

def check_and_complete_course(enrollment):
    course = enrollment.course
    total_lessons = Lesson.objects.filter(module__course=course).count()
    completed_lessons = LessonProgress.objects.filter(enrollment=enrollment, is_completed=True).count()

    if total_lessons > 0 and total_lessons == completed_lessons:
        enrollment.is_completed = True
        enrollment.completed_at = timezone.now()
        enrollment.status = 'completed'
        enrollment.save(update_fields=['is_completed', 'completed_at', 'status'])

        return True
    
    return False

def get_resume_lesson(enrollment):
    course = enrollment.course

    lessons = Lesson.objects.filter(
        module__course=course
    ).order_by('module__position', 'position')

    completed_ids = set(
        LessonProgress.objects.filter(
            enrollment=enrollment,
            is_completed=True
        ).values_list('lesson_id', flat=True)
    )

    for lesson in lessons:
        # Skip free lessons in progression
        if lesson.is_free:
            continue

        # Return first non-free lesson that's not completed
        if lesson.id not in completed_ids:
            return lesson

    return None


def require_active_enrollment(user, course):
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