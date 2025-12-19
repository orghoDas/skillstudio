from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Sum
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
        completed_enrollments = enrollments.filter(completed=True).count()

        completion_rate = round((completed_enrollments / total_enrollments * 100), 2) if total_enrollments > 0 else 0

        progress_data = []
        total_lessons = Lesson.objects.filter(course=course).count()

        if total_lessons > 0:
            for enrollment in enrollments:
                completed_lessons = LessonProgress.objects.filter(
                    enrollment=enrollment,
                    completed=True
                ).count()
                
                progress_data.append((completed_lessons / total_lessons) * 100)
                
        avg__progress = round(sum(progress_data) / len(progress_data), 2) if progress_data else 0

        drop_off = (LessonProgress.objects
                    .filter(lesson__module__course=course)
                    .values('lesson_id', 'lesson__title')
                    .annotate(total_views=Count('id'))
                    .order_by('total_views').first()
                    )
        
        total_watch_time = LessonProgress.objects.filter(lesson__module__course=course).aggregate(total_time=Sum('watch_time'))['total'] or 0

        return Response({
            'course': course.title,
            'total_enrollments': total_enrollments,
            'completed_enrollments': completed_enrollments,
            'completion_rate': completion_rate,
            'average_progress': avg__progress,
            'highest_drop_off_lesson': drop_off,
            'total_watch_time_seconds': total_watch_time
        })
    
