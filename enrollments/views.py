from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, Q, F, FloatField, ExpressionWrapper, Sum
from django.http import HttpResponse
import csv

from accounts.permissions import IsInstructor
from courses.models import Course, Lesson
from .models import Enrollment, LessonProgress, Wishlist
from .serializers import (
    EnrollmentListSerializer,
    EnrollmentDetailSerializer,
    EnrollmentCreateSerializer,
    LessonProgressSerializer,
    LessonProgressDetailSerializer,
    WishlistSerializer,
    WishlistCreateSerializer,
    EnrollmentStatsSerializer,
    CourseProgressStatsSerializer,
)
from .services import (
    mark_lesson_completed,
    check_and_complete_course,
    auto_complete_lesson,
    get_resume_lesson,
    get_next_lesson,
)


# ===========================
# 🎓 Enrollment Views
# ===========================

class EnrollmentListView(generics.ListAPIView):
    """List all enrollments for the authenticated user."""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentListSerializer

    def get_queryset(self):
        queryset = Enrollment.objects.filter(
            user=self.request.user
        ).select_related('course', 'course__instructor').order_by('-enrolled_at')
        
        # Filter by course ID if provided
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        # Filter by course slug if provided
        course_slug = self.request.query_params.get('course_slug')
        if course_slug:
            queryset = queryset.filter(course__slug=course_slug)
        
        # Filter by status if provided
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset


class EnrollmentDetailView(generics.RetrieveAPIView):
    """Get detailed enrollment information."""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentDetailSerializer

    def get_queryset(self):
        return Enrollment.objects.filter(
            user=self.request.user
        ).select_related('course', 'course__instructor')


class EnrollCourseView(generics.CreateAPIView):
    """Enroll in a course."""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrollment = serializer.save()
        
        # Determine if it's a new enrollment or reactivation
        was_reactivated = enrollment.status == 'active' and Enrollment.objects.filter(
            user=request.user,
            course_id=serializer.validated_data['course_id']
        ).exists()
        
        response_data = EnrollmentDetailSerializer(enrollment).data
        response_data['was_reactivated'] = was_reactivated
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class CancelEnrollmentView(APIView):
    """Cancel an enrollment."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, enrollment_id):
        enrollment = get_object_or_404(
            Enrollment,
            id=enrollment_id,
            user=request.user,
            status='active'
        )

        enrollment.status = 'canceled'
        enrollment.save(update_fields=['status'])

        return Response({
            'message': 'Enrollment canceled successfully.',
            'enrollment_id': enrollment.id
        })


class MyLearningView(generics.ListAPIView):
    """Get all active enrollments (My Learning page)."""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentListSerializer

    def get_queryset(self):
        return Enrollment.objects.filter(
            user=self.request.user,
            status='active'
        ).select_related('course', 'course__instructor').order_by('-enrolled_at')


class CompletedCoursesView(generics.ListAPIView):
    """Get all completed courses."""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentListSerializer

    def get_queryset(self):
        return Enrollment.objects.filter(
            user=self.request.user,
            status='completed'
        ).select_related('course', 'course__instructor').order_by('-completed_at')


# ===========================
# 📊 Progress Tracking Views
# ===========================

class CourseProgressView(APIView):
    """Get overall progress for a specific course."""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course_id=course_id,
            status='active'
        )

        total_lessons = Lesson.objects.filter(
            module__course_id=course_id,
            is_free=False
        ).count()

        if total_lessons == 0:
            return Response({
                'course_id': course_id,
                'course_title': enrollment.course.title,
                'total_lessons': 0,
                'completed_lessons': 0,
                'progress_percentage': 0,
                'is_completed': False,
            })

        completed_lessons = enrollment.lesson_progress.filter(
            is_completed=True
        ).count()

        progress_percentage = round((completed_lessons / total_lessons * 100), 2)

        # Auto-complete course if all lessons done
        if completed_lessons == total_lessons and not enrollment.is_completed:
            enrollment.is_completed = True
            enrollment.status = 'completed'
            enrollment.completed_at = timezone.now()
            enrollment.save(update_fields=['is_completed', 'status', 'completed_at'])

        return Response({
            'course_id': course_id,
            'course_title': enrollment.course.title,
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': progress_percentage,
            'is_completed': enrollment.is_completed,
        })


class LessonProgressView(APIView):
    """Get progress for a specific lesson."""
    permission_classes = [IsAuthenticated]

    def get(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course=lesson.module.course,
            status='active'
        )

        progress, _ = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            user=request.user,
            lesson=lesson
        )

        serializer = LessonProgressDetailSerializer(progress)
        return Response(serializer.data)


class LessonWatchTimeView(APIView):
    """Update lesson watch time."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def patch(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course=lesson.module.course,
            status='active'
        )

        watch_time = request.data.get('watch_time', 0)
        if watch_time < 0:
            return Response(
                {'error': 'Watch time cannot be negative.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        progress, _ = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            user=request.user,
            lesson=lesson
        )

        # Update watch time (don't exceed lesson duration)
        max_duration = lesson.duration_seconds
        progress.watch_time = min(watch_time, max_duration)
        progress.save(update_fields=['watch_time'])

        # Auto-complete lesson if threshold reached
        if auto_complete_lesson(progress) and not progress.is_completed:
            mark_lesson_completed(enrollment, lesson)
            check_and_complete_course(enrollment)

        return Response({
            'watch_time': progress.watch_time,
            'completed': progress.is_completed,
            'progress_percentage': round((progress.watch_time / max_duration * 100), 2) if max_duration > 0 else 0,
        })


class ResumeLessonView(APIView):
    """Get the next lesson to resume for a course."""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course_id=course_id,
            status='active'
        )

        lesson = get_resume_lesson(enrollment)

        if not lesson:
            return Response({
                'message': 'All lessons completed.',
                'completed': True
            })

        return Response({
            'lesson_id': lesson.id,
            'lesson_title': lesson.title,
            'module_id': lesson.module.id,
            'module_title': lesson.module.title,
            'position': lesson.position,
        })


class NextLessonView(APIView):
    """Get the next lesson after current one."""
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
                'message': 'No more lessons.',
                'completed': True
            })

        return Response({
            'lesson_id': next_lesson.id,
            'lesson_title': next_lesson.title,
            'module_id': next_lesson.module.id,
            'module_title': next_lesson.module.title,
            'position': next_lesson.position,
        })


class CompleteLessonView(APIView):
    """Manually mark a lesson as completed."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course=lesson.module.course,
            status='active'
        )

        progress = mark_lesson_completed(enrollment, lesson)
        check_and_complete_course(enrollment)

        return Response({
            'message': 'Lesson marked as completed.',
            'lesson_id': lesson.id,
            'completed_at': progress.completed_at,
        })


# ===========================
# 📋 Wishlist Views
# ===========================

class WishlistListView(generics.ListAPIView):
    """List all wishlist items for the authenticated user."""
    permission_classes = [IsAuthenticated]
    serializer_class = WishlistSerializer

    def get_queryset(self):
        return Wishlist.objects.filter(
            user=self.request.user
        ).select_related('course', 'course__instructor').order_by('-added_at')


class AddToWishlistView(generics.CreateAPIView):
    """Add a course to wishlist."""
    permission_classes = [IsAuthenticated]
    serializer_class = WishlistCreateSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if already in wishlist
        course_id = serializer.validated_data['course_id']
        existing = Wishlist.objects.filter(
            user=request.user,
            course_id=course_id
        ).exists()
        
        if existing:
            return Response(
                {'message': 'Course already in wishlist.'},
                status=status.HTTP_200_OK
            )
        
        wishlist = serializer.save()
        response_data = WishlistSerializer(wishlist).data
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class RemoveFromWishlistView(generics.DestroyAPIView):
    """Remove a course from wishlist."""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({
            'message': 'Course removed from wishlist.',
            'course_id': instance.course.id
        }, status=status.HTTP_200_OK)


class CheckWishlistView(APIView):
    """Check if a course is in wishlist."""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        in_wishlist = Wishlist.objects.filter(
            user=request.user,
            course_id=course_id
        ).exists()
        
        return Response({'in_wishlist': in_wishlist})


# ===========================
# 📊 Statistics & Analytics Views
# ===========================

class EnrollmentStatsView(APIView):
    """Get overall enrollment statistics for the authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        enrollments = Enrollment.objects.filter(user=user)

        total_enrollments = enrollments.count()
        active_enrollments = enrollments.filter(status='active').count()
        completed_enrollments = enrollments.filter(status='completed').count()
        canceled_enrollments = enrollments.filter(status='canceled').count()
        
        total_courses_enrolled = enrollments.values('course').distinct().count()
        
        # Calculate average progress
        active_enroll = enrollments.filter(status='active')
        if active_enroll.exists():
            progress_sum = 0
            for enrollment in active_enroll:
                total_lessons = Lesson.objects.filter(
                    module__course=enrollment.course,
                    is_free=False
                ).count()
                if total_lessons > 0:
                    completed = enrollment.lesson_progress.filter(is_completed=True).count()
                    progress_sum += (completed / total_lessons) * 100
            average_progress = round(progress_sum / active_enroll.count(), 2) if active_enroll.count() > 0 else 0
        else:
            average_progress = 0
        
        # Calculate total watch time in hours
        total_watch_time = LessonProgress.objects.filter(
            user=user
        ).aggregate(total=Sum('watch_time'))['total'] or 0
        total_watch_time_hours = round(total_watch_time / 3600, 2)

        stats = {
            'total_enrollments': total_enrollments,
            'active_enrollments': active_enrollments,
            'completed_enrollments': completed_enrollments,
            'canceled_enrollments': canceled_enrollments,
            'total_courses_enrolled': total_courses_enrolled,
            'average_progress': average_progress,
            'total_watch_time_hours': total_watch_time_hours,
        }

        serializer = EnrollmentStatsSerializer(stats)
        return Response(serializer.data)


class LearningProgressDashboardView(APIView):
    """Get detailed progress for all enrolled courses."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        enrollments = Enrollment.objects.filter(
            user=request.user,
            status='active'
        ).select_related('course')

        progress_data = []
        for enrollment in enrollments:
            total_lessons = Lesson.objects.filter(
                module__course=enrollment.course,
                is_free=False
            ).count()
            
            completed_lessons = enrollment.lesson_progress.filter(
                is_completed=True
            ).count()
            
            total_duration = Lesson.objects.filter(
                module__course=enrollment.course,
                is_free=False
            ).aggregate(total=Sum('duration_seconds'))['total'] or 0
            
            watched_time = enrollment.lesson_progress.aggregate(
                total=Sum('watch_time')
            )['total'] or 0
            
            progress_percentage = 0
            if total_lessons > 0:
                progress_percentage = round((completed_lessons / total_lessons) * 100, 2)
            
            progress_data.append({
                'course_id': enrollment.course.id,
                'course_title': enrollment.course.title,
                'total_lessons': total_lessons,
                'completed_lessons': completed_lessons,
                'progress_percentage': progress_percentage,
                'total_duration_seconds': total_duration,
                'watched_time_seconds': watched_time,
                'is_completed': enrollment.is_completed,
                'enrolled_at': enrollment.enrolled_at,
                'completed_at': enrollment.completed_at,
            })

        serializer = CourseProgressStatsSerializer(progress_data, many=True)
        return Response(serializer.data)


# ===========================
# 👨‍🏫 Instructor Analytics (CSV Export)
# ===========================

class InstructorLessonAnalyticsCSVView(APIView):
    """Export lesson analytics as CSV for instructors."""
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        instructor = request.user
        course = get_object_or_404(Course, id=course_id, instructor=instructor)
        
        lessons = Lesson.objects.filter(module__course=course).annotate(
            started_count=Count('lessonprogress', distinct=True),
            completed_count=Count(
                'lessonprogress',
                filter=Q(lessonprogress__is_completed=True),
                distinct=True
            )
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
        writer.writerow([
            'Lesson ID', 'Lesson Title', 'Started Enrollments',
            'Completed Enrollments', 'Drop-off Count', 'Drop-off Rate (%)'
        ])

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
