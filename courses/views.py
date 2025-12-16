from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from django.db.models import F

from .models import Lesson, User
from .serializers import LessonDataSerializer
from enrollments.models import Enrollment

class LessonDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)

        user = request.user
        course = lesson.module.course

        Lesson.objects.filter(id=lesson.id).update(view_count=F('view_count') + 1)

        if not user.is_authenticated:
            if lesson.is_free:
                serializer = LessonDataSerializer(lesson)
                return Response(serializer.data)
            raise PermissionDenied("Login required to access this lesson.")
        
        if user.is_staff or user.is_superuser:
            serializer = LessonDataSerializer(lesson)
            return Response(serializer.data)
        
        if course.instructor == user:
            serializer = LessonDataSerializer(lesson)
            return Response(serializer.data)
        
        if lesson.is_free:
            serializer = LessonDataSerializer(lesson)
            return Response(serializer.data)
        
        is_enrolled = Enrollment.objects.filter(user=user, course=course, active=True).exists()
        if not is_enrolled:
            raise PermissionDenied("You must be enrolled in the course to access this lesson.")
        
        serializer = LessonDataSerializer(lesson)
        return Response(serializer.data)