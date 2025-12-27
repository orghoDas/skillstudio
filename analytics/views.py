from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Sum, Q
from django.shortcuts import get_object_or_404

from courses.models import Course, Lesson
from enrollments.models import Enrollment, LessonProgress
from accounts.permissions import IsInstructor

# Create your views here.

class InstructorCourseAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        instructor = request.user

        course = get_object_or_404(Course, id=course_id, instructor=instructor)

        enrollments = Enrollment.objects.filter(course=course)
        total_enrollments = enrollments.count()
        completed_enrollments = enrollments.filter(is_completed=True).count()

        completion_rate = round((completed_enrollments / total_enrollments * 100), 2) if total_enrollments > 0 else 0

        total_lessons = Lesson.objects.filter(module__course=course).count()

        progress_queryset = (
            LessonProgress.objects.filter(lesson__module__course=course, is_completed=True)
            .values('enrollment')
            .annotate(completed_lessons=Count('id'))
        )

        progress_percentages = [
            (item['completed_lessons'] / total_lessons) * 100 for item in progress_queryset
        ] if total_lessons > 0 else []

        avg_progress = round(sum(progress_percentages) / len(progress_percentages), 2) if progress_percentages else 0

        drop_off = (LessonProgress.objects
                    .filter(lesson__module__course=course)
                    .values('lesson_id', 'lesson__title')
                    .annotate(total_views=Count('enrollment', distinct=True))
                    .order_by('total_views').first()
                    )
        
        total_watch_time = LessonProgress.objects.filter(lesson__module__course=course).aggregate(total_time=Sum('watch_time'))['total_time'] or 0

        return Response({
    'course': course.title,
    'total_enrollments': total_enrollments,
    'completed_enrollments': completed_enrollments,
    'completion_rate': completion_rate,
    'average_progress': avg_progress,
    'highest_drop_off_lesson': drop_off,
    'total_watch_time_seconds': total_watch_time
})

    
