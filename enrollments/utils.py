from django.utils import timezone
from courses.models import Lesson
from .models import LessonProgress

def check_and_complete_course(enrollment):
    course = enrollment.course
    total_lessons = Lesson.objects.filter(module__course=course).count()
    completed_lessons = LessonProgress.objects.filter(enrollment=enrollment, is_completed=True).count()

    if total_lessons > 0 and total_lessons == completed_lessons:
        enrollment.is_completed = True
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=['is_completed', 'completed_at'])

        return True
    
    return False

def get_resume_lesson(enrollment):
    return (
        Lesson.objects
        .filter(
            module__course=enrollment.course)
            .exclude(
                id__in=LessonProgress.objects.filter(
                    enrollment=enrollment,
                    is_completed=True
                ).values_list('lesson_id', flat=True)
            )
        .order_by('module__positon', 'position')
        .first()
    )

