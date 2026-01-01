import csv
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Count, Q, Avg, Sum, F, ExpressionWrapper, FloatField
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404
from enrollments.constants import LESSON_COMPLETION_THRESHOLD

from accounts.permissions import IsInstructor

from .models import LessonProgress, Enrollment
from courses.models import Course, Lesson
from .serializers import LessonProgressSerializer
from .utils import check_and_complete_course, get_resume_lesson

from .services import mark_lesson_completed, check_and_mark_course_completed, auto_complete_lesson, get_previous_lesson, get_next_lesson

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

        enrollment = get_object_or_404(Enrollment, user=user, course=course, status='active')
        
        progress, _ = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            user=user,
            lesson=lesson)
        
        added_time = request.data.get('watch_time')

        try:
            added_time = int(added_time)

        except (TypeError, ValueError):
            raise ValidationError({"detail": "Invalid watch time."})
        
        if added_time <= 0:
            raise ValidationError({"detail": "Invalid watch time."})
        
        progress.watch_time = min(progress.watch_time + added_time, lesson.duration_seconds)

        if (lesson.duration_seconds > 0 and progress.watch_time >= lesson.duration_seconds * LESSON_COMPLETION_THRESHOLD and not progress.is_completed):
            progress.is_completed = True
            progress.completed_at = timezone.now()

        progress.save(update_fields=['watch_time', 'is_completed', 'completed_at'])

        if progress.is_completed:
            check_and_complete_course(progress.enrollment)

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

        progress_percentage = round((completed_lessons / total_lessons * 100), 2)

        if completed_lessons == total_lessons and not enrollment.is_completed:
            enrollment.is_completed = True
            enrollment.status = 'completed'
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=['is_completed', 'status', 'completed_at'])


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
    

class InstructorLessonDropoffView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        instructor = request.user

        course = get_object_or_404(Course, id=course_id, instructor=instructor)
        lessons = Lesson.objects.filter(module__course=course).annotate(
            started_count=Count('lessonprogress', distinct=True),
            completed_count=Count('lessonprogress', filter=Q(lessonprogress__is_completed=True), distinct=True)
        ).annotate(
            drop_off_count=F('started_count') - F('completed_count'),
            drop_off_rate=ExpressionWrapper(
                (F('drop_off_count') * 100.0) / F('started_count'),
                output_field=FloatField()
            )
        )

        data = []

        for lesson in lessons:
            data.append({
                'lesson_id': lesson.id,
                'lesson_title': lesson.title,
                'started_enrollments': lesson.started_count,
                'completed_enrollments': lesson.completed_count,
                'drop_off_count': lesson.drop_off_count,
                'drop_off_rate_percentage': lesson.drop_off_rate,
            })

        return Response(data)
    

class InstructorLessonAnalyticsCSVView(APIView):
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        instructor = request.user

        course = get_object_or_404(Course, id=course_id, instructor=instructor)
        lessons = Lesson.objects.filter(module__course=course).annotate(
            started_count=Count('lessonprogress', distinct=True),
            completed_count=Count('lessonprogress', filter=Q(lessonprogress__is_completed=True), distinct=True)
        ).annotate(
            drop_off_count=F('started_count') - F('completed_count'),
            drop_off_rate=ExpressionWrapper(
                (F('drop_off_count') * 100.0) / F('started_count'),
                output_field=FloatField()
            )
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="lesson_analytics_course_{course_id}.csv"'

        writer = csv.writer(response)
        writer.writerow(['Lesson ID', 'Lesson Title', 'Started Enrollments', 'Completed Enrollments', 'Drop-off Count', 'Drop-off Rate (%)'])

        for lesson in lessons:
            writer.writerow([
                lesson.id,
                lesson.title,
                lesson.started_count,
                lesson.completed_count,
                lesson.drop_off_count,
                round(lesson.drop_off_rate or 0, 2),
            ])

        return response
    

class EnrollCourseView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, course_id):
        user = request.user
        course = get_object_or_404(Course, id=course_id)

        enrollment, created = Enrollment.objects.get_or_create(
            user=user,
            course=course,
            defaults={'status': 'active'}
        )

        if not created:
            if enrollment.status == 'canceled':
                enrollment.status = 'active'
                enrollment.completed_at = None
                enrollment.is_completed = False
                enrollment.save()
                return Response({'enrolled': True, 'resumed': True})

            return Response({'detail': 'Already enrolled.'}, status=400)

        return Response({'enrolled': True}, status=201)
    

class CancelEnrollmentView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, course_id):
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course_id=course_id,
            status='active'
        )

        enrollment.status = 'canceled'
        enrollment.save(update_fields=['status'])

        return Response({'canceled': True})
    

class ResumeLessonView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        user = request.user

        enrollment = get_object_or_404(
            Enrollment,
            user=user,
            course_id=course_id,
            status='active'
        )

        lesson = get_resume_lesson(enrollment)

        if not lesson:
            return Response({
                "detail": "Course completed.",
                "completed": True
            })

        return Response({
            "lesson_id": lesson.id,
            "lesson_title": lesson.title,
            "module_id": lesson.module.id,
            "module_title": lesson.module.title,
        })


class NextLessonView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id, lesson_id):
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course_id=course_id,
            status='active'
        )

        current_lesson = get_object_or_404(Lesson, id=lesson_id)

        next_lesson = get_next_lesson(enrollment, current_lesson)

        if not next_lesson:
            return Response({
                "detail": "No next lesson.",
                "completed": True
            })

        return Response({
            "lesson_id": next_lesson.id,
            "lesson_title": next_lesson.title,
            "module_title": next_lesson.module.title,
        })
