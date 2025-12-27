from django.shortcuts import render
from django.db.models import Count, Q, Avg, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404

from accounts.permissions import IsInstructor

from .models import LessonProgress, Enrollment
from courses.models import Course, Lesson
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
    

class InstructorDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user

        courses = Course.objects.filter(instructor=instructor)
        total_courses = courses.count()

        enrollments = Enrollment.objects.filter(course__in=courses)
        total_enrollments = enrollments.count()

        total_students = enrollments.values('user').distinct().count()

        course_progress = []

        for course in courses:
            course_enrollments = Enrollment.objects.filter(course=course)
            total = course_enrollments.count()

            if total == 0:
                continue

            completed = course_enrollments.filter(is_completed=True).count()
            completion_rate = round((completed / total * 100), 2)
            course_progress.append({
                'course_id': course.id,
                'course_title': course.title,
                'total_enrollments': total,
                'completed_enrollments': completed,
                'completion_rate': completion_rate
            })

        avg_completion_rate = round(sum(c['completion_rate'] for c in course_progress) / len(course_progress), 2) if course_progress else 0

        total_watch_time = LessonProgress.objects.filter(lesson__module__course__in=courses).aggregate(total_time=Sum('watch_time'))['total_time'] or 0

        top_course = max(course_progress, key=lambda x: x['completion_rate']) if course_progress else None
        weakest_course = min(course_progress, key=lambda x: x['completion_rate']) if course_progress else None

        return Response({
            'total_courses': total_courses,
            'total_enrollments': total_enrollments,
            'total_students': total_students,
            'average_completion_rate': avg_completion_rate,
            'total_watch_time_seconds': total_watch_time,
            'top_performing_course': top_course,
            'weakest_performing_course': weakest_course,
        })
    

class InstructorCourseComparisonView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user
        courses = Course.objects.filter(instructor=instructor)

        data = []

        for course in courses:
            enrollments = Enrollment.objects.filter(course=course)
            total_enrollments = enrollments.count()

            completed_enrollments = enrollments.filter(is_completed=True).count()
            completion_rate = round((completed_enrollments / total_enrollments * 100), 2) if total_enrollments > 0 else 0

            lessons = Lesson.objects.filter(module__course=course)
            total_lessons = lessons.count() 

            avg_watch_time = LessonProgress.objects.filter(lesson__in=lessons).aggregate(avg_time=Avg('watch_time'))['avg_time'] or 0

            data.append({
                'course_id': course.id,
                'course_title': course.title,
                'total_enrollments': total_enrollments,
                'average_watch_time_seconds': round(avg_watch_time, 2),
                'total_lessons': total_lessons,
            })

        return Response(data)