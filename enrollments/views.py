from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import LessonProgress, Enrollment
from courses.models import Lesson
from .serializers import LessonProgressSerializer

# Create your views here.

class LessonProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        user = request.user
        lesson = get_object_or_404(Lesson, id=lesson_id)
        course = lesson.module.course

        enrollment = get_object_or_404(Enrollment, user=user, course=course, status='active')
        
        progress, created = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            user=user,
            lesson=lesson,
        )

        serializer = LessonProgressSerializer(progress)
        return Response(serializer.data)
    
    def patch(self, request, lesson_id):
        user = request.user
        lesson = get_object_or_404(Lesson, id=lesson_id)  

        enrollment = get_object_or_404(Enrollment, user=user, course=lesson.module.course, status='active')

        progress = get_object_or_404(LessonProgress, enrollment=enrollment, user=user, lesson=lesson)
        
        if not progress.is_completed:
            progress.is_completed = True
            progress.completed_at = timezone.now()
            progress.save()

        serializer = LessonProgressSerializer(progress)
        return Response(serializer.data)
    
