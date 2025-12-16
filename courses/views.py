from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Lesson
from .serializers import LessonDataSerializer
from enrollments.models import Enrollment

class LessonDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)

        user = request.user
        course = lesson.module.course

        if user.is_staff or user.is_superuser:
            serializer = LessonDataSerializer(lesson)
            return Response(serializer.data)
        
        if course.instructor == user:
            serializer = LessonDataSerializer(lesson)
            return Response(serializer.data)
        
        is_enrolled = Enrollment.objects.filter(user=user, course=course).exists()

        if not is_enrolled:
            raise PermissionDenied("You are not enrolled in this course.")
        
        serializer = LessonDataSerializer(lesson)
        return Response(serializer.data)