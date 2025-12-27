from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import LessonProgress, Enrollment
from courses.models import Lesson
from .serializers import LessonProgressSerializer
from .utils import check_and_complete_course, get_resume_lesson

from .services import mark_lesson_completed, check_and_mark_course_completed

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
    

class LessonWatchTimeView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, lesson_id):
        user = request.user
        lesson = get_object_or_404(Lesson, id=lesson_id)
        course = lesson.module.course

        if not Enrollment.objects.filter(user=user, course=course, status='active').exists():
            raise PermissionDenied("You are not enrolled in this course.")
        
        progress, _ = LessonProgress.objects.get_or_create(
            user = user,
            lesson = lesson,)
        
        added_time = int(request.data.get('watch_time', 0))

        if not isinstance(added_time, int) or added_time <= 0:
            raise ValidationError({"detail": "Invalid watch time."})
        
        progress.watch_time += added_time

        if (lesson.duration_seconds > 0 and progress.watch_time >= lesson.duration_seconds and not progress.is_completed):
            progress.is_completed = True
            progress.completed_at = timezone.now()

        if progress.is_completed:
            check_and_complete_course(progress.enrollment)


        progress.save(update_fields=['watch_time'])

        return Response({
            "watch_time": progress.watch_time,
            'completed': progress.is_completed
        })
    

class ResumeLessonView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        enrollment = get_object_or_404(Enrollment, user=request.user, course_id=course_id, status='active')

        lesson = get_resume_lesson(enrollment)

        if not lesson:
            return Response({"detail": "All lessons completed.",
                            'completed': True})
        
        return Response({
            "lesson_id": lesson.id,
            "lesson_title": lesson.title,
            "module_title": lesson.module.title,
        })
    

class CourseProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        enrollment = get_object_or_404(Enrollment, user=user, course_id=course_id, status='active')

        total_lessons = Lesson.objects.filter(module__course_id=course_id).count()

        if total_lessons == 0:
            return Response({
                'course_id': course_id,
                "total_lessons": 0,
                "completed_lessons": 0,
                "progress_percentage": 0,
            })

        completed_lessons = LessonProgress.objects.filter(enrollment=enrollment, is_completed=True).count()

        progress_percentage = round((completed_lessons / total_lessons * 100), 2) if total_lessons > 0 else 0

        return Response({
            'course_id': course_id,
            'course_title': enrollment.course.title,
            "total_lessons": total_lessons,
            "completed_lessons": completed_lessons,
            "progress_percentage": progress_percentage,
            'is_completed': enrollment.is_completed
        })