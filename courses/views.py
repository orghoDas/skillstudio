from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from .models import Lesson
from enrollments.models import Enrollment

class LessonDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        lesson = Lesson.objects.select_related('module__course').get(id=lesson_id)

        user = request.user
        course = lesson.module.course

        if user.is_staff or user.is_superuser:
            return Response({'lesson': lesson.title})
        
        if course.instructor == user:
            return Response({'lesson': lesson.title})
        
        is_enrolled = Enrollment.objects.filter(user=user, course=course).exists()

        if not is_enrolled:
            raise PermissionDenied("You are not enrolled in this course.")
        
        return Response({'id': lesson.id, 
                         'title': lesson.title, 
                         'content_type': lesson.content_type,
                         'video_url': lesson.video_url,})