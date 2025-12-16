from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import LessonProgress, Enrollment
from courses.models import Lesson

# Create your views here.

class LessonProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        user = request.user
        lesson = Lesson.objects.get(id=lesson_id)
        course = lesson.module.course

        if not Enrollment.objects.filter(user=user, course=course, active=True).exists():
            raise PermissionDenied("You must be enrolled in the course to update lesson progress.")
        
        progress, created = LessonProgress.objects.get_or_create(
            user=user,
            lesson=lesson,
            defaults={'is_completed': False, 'last_updated': timezone.now()}
        )

        return Response({'started': True, 
                         'created': created,
        })
    
    def patch(self, request, lesson_id):
        user = request.user
        lesson = lesson.objects.get(id=lesson_id)  

        progress = LessonProgress.objects.filter(user=user, lesson=lesson)
        progress.is_completed = True
        progress.is_completed = timezone.now()
        progress.save()

        return Response({'completed': True})
    
    
