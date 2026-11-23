from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from django.db.models import Count, F, FloatField, Max, Q, Sum
from django.db.models.functions import Cast, Coalesce, NullIf
from django.http import HttpResponse
import csv

from accounts.permissions import IsInstructor
from enrollments.constants import ACCESS_STATUSES
from students.activity import learning_timezone
from courses.models import Course, Lesson
from courses.policies import can_view_course_catalog
from .models import Enrollment, LessonProgress, Wishlist
from assessments.services import is_lesson_assessment_completed
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
    require_unlocked_lesson,
    cancel_enrollments,
    check_and_complete_course,
    auto_complete_lesson,
    get_resume_lesson,
    ordered_course_lessons,
    get_lesson_completion_stats,
    lesson_progress_percentage,
    update_lesson_watch_progress,
    with_enrollment_progress,
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
        ).select_related('course__instructor__profile')
        
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
        
        if self.request.query_params.get('accessible') == 'true':
            queryset = queryset.filter(status__in=ACCESS_STATUSES)
        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(course__title__icontains=search)

        ordering = self.request.query_params.get('ordering')
        queryset = with_enrollment_progress(queryset, completed_ids=True)
        sort = '-enrolled_at'
        if ordering == 'title':
            sort = 'course__title'
        elif ordering == '-last_accessed':
            queryset = queryset.annotate(last_accessed=Coalesce(Max('lesson_progress__updated_at'), F('enrolled_at')))
            sort = '-last_accessed'
        elif ordering == '-progress':
            queryset = with_enrollment_progress(queryset).annotate(
                progress=Coalesce(Cast('required_completed_count', FloatField()) / NullIf(F('required_count'), 0), 0.0),
            )
            sort = '-progress'
        return queryset.order_by(sort, '-pk')


class EnrollmentDetailView(generics.RetrieveAPIView):
    """Get detailed enrollment information."""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentDetailSerializer

    def get_queryset(self):
        return Enrollment.objects.filter(
            user=self.request.user
        ).select_related('course__instructor__profile')


class EnrollCourseView(generics.CreateAPIView):
    """Enroll in a course, paying from the wallet if it is a paid course.

    Idempotent: re-enrolling in a course you already own returns 200 with
    ``outcome = "already_enrolled"`` and charges nothing.
    Responses: 201 created · 200 reactivated / already_enrolled ·
    400 {"detail", "code"} (insufficient_balance, own_course, invalid_coupon,
    course_unavailable).
    """
    throttle_scope = "enroll"
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentCreateSerializer

    def create(self, request, *args, **kwargs):
        from payments.services import OUTCOME_CREATED, PurchaseError, purchase_course

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = purchase_course(
                request.user,
                serializer.validated_data['course_id'],
                coupon_code=serializer.validated_data.get('coupon_code') or None,
            )
        except PurchaseError as exc:
            return Response(
                {'detail': exc.message, 'code': exc.code},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_data = EnrollmentDetailSerializer(result.enrollment).data
        response_data['outcome'] = result.outcome
        response_data['was_reactivated'] = result.outcome == 'reactivated'
        response_data['charged_amount'] = str(result.charged_amount)
        response_data['payment_id'] = result.payment.id if result.payment else None

        return Response(
            response_data,
            status=status.HTTP_201_CREATED if result.outcome == OUTCOME_CREATED else status.HTTP_200_OK,
        )


class CancelEnrollmentView(APIView):
    """Cancel an enrollment."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, enrollment_id):
        canceled = cancel_enrollments(Enrollment.objects.filter(
            id=enrollment_id,
            user=request.user,
        ))
        if not canceled:
            return Response({'error': 'Enrollment not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'message': 'Enrollment canceled successfully.',
            'enrollment_id': enrollment_id
        })


class MyLearningView(generics.ListAPIView):
    """Get all active enrollments (My Learning page)."""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentListSerializer

    def get_queryset(self):
        queryset = Enrollment.objects.filter(
            user=self.request.user,
            status='active'
        ).select_related('course__instructor__profile').order_by('-enrolled_at', '-pk')
        return with_enrollment_progress(queryset, completed_ids=True)


class CompletedCoursesView(generics.ListAPIView):
    """Get all completed courses."""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentListSerializer

    def get_queryset(self):
        queryset = Enrollment.objects.filter(
            user=self.request.user,
            status='completed'
        ).select_related('course__instructor__profile').order_by('-completed_at', '-pk')
        return with_enrollment_progress(queryset, completed_ids=True)


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
            status__in=ACCESS_STATUSES
        )

        stats = get_lesson_completion_stats(enrollment)

        if stats['total_lessons'] == 0:
            return Response({
                'course_id': course_id,
                'course_title': enrollment.course.title,
                'total_lessons': 0,
                'completed_lessons': 0,
                'progress_percentage': 0,
                'is_completed': False,
            })

        return Response({
            'course_id': course_id,
            'course_title': enrollment.course.title,
            'total_lessons': stats['total_lessons'],
            'completed_lessons': stats['completed_lessons'],
            'progress_percentage': stats['progress_percentage'],
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
            status__in=ACCESS_STATUSES
        )

        progress = LessonProgress.objects.filter(
            enrollment=enrollment,
            user=request.user,
            lesson=lesson
        ).first()

        if progress:
            serializer = LessonProgressDetailSerializer(progress)
            return Response(serializer.data)

        return Response({
            'id': None,
            'lesson': {
                'id': lesson.id,
                'title': lesson.title,
                'duration_seconds': lesson.duration_seconds,
                'module_id': lesson.module.id,
                'module_title': lesson.module.title,
                'position': lesson.position,
            },
            'watch_time': 0,
            'is_completed': False,
            'completed_at': None,
            'progress_percentage': 0,
            'started_at': None,
        })


class LessonWatchTimeView(APIView):
    """Update lesson watch time using incremental deltas."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, lesson_id):
        lesson = get_object_or_404(Lesson, id=lesson_id)
        enrollment = get_object_or_404(
            Enrollment,
            user=request.user,
            course=lesson.module.course,
            status__in=ACCESS_STATUSES
        )
        require_unlocked_lesson(enrollment, lesson)

        if 'watch_time' in request.data and 'watch_time_delta' not in request.data:
            raise DjangoValidationError('Use watch_time_delta; absolute watch_time updates are not accepted.')

        watch_time_delta = request.data.get('watch_time_delta', 0)
        try:
            watch_time_delta = int(watch_time_delta)
        except (TypeError, ValueError, OverflowError) as exc:
            raise DjangoValidationError('Watch time delta must be an integer number of seconds.') from exc

        local_zone = learning_timezone(request)
        progress = update_lesson_watch_progress(
            enrollment=enrollment,
            lesson=lesson,
            watch_time_delta=watch_time_delta,
            local_zone=local_zone,
        )

        # Auto-complete lesson if threshold reached
        if (
            not progress.is_completed and auto_complete_lesson(progress)
            and is_lesson_assessment_completed(request.user, lesson)
        ):
            progress = mark_lesson_completed(enrollment, lesson, local_zone=local_zone)
            check_and_complete_course(enrollment)

        max_duration = lesson.duration_seconds
        return Response({
            'watch_time': progress.watch_time,
            'accepted_delta': watch_time_delta,
            'completed': progress.is_completed,
            'progress_percentage': round((progress.watch_time / max_duration * 100), 2) if max_duration > 0 else 0,
        })


class ResumeLessonView(APIView):
    """Get the next lesson to resume for a course."""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        enrollment = get_object_or_404(
            Enrollment.objects.select_related('course'),
            user=request.user,
            course_id=course_id,
            status__in=ACCESS_STATUSES
        )

        if not can_view_course_catalog(request.user, enrollment.course):
            return Response({'error': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)
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
            Enrollment.objects.select_related('course'),
            user=request.user,
            course_id=course_id,
            status__in=ACCESS_STATUSES
        )

        if not can_view_course_catalog(request.user, enrollment.course):
            return Response({'error': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)
        lessons = ordered_course_lessons(enrollment.course)
        lesson_order = {lesson.pk: index for index, lesson in enumerate(lessons)}
        if lesson_id not in lesson_order:
            return Response({'error': 'Lesson not found.'}, status=status.HTTP_404_NOT_FOUND)
        next_lesson = get_resume_lesson(enrollment, lessons=lessons)

        if not next_lesson:
            return Response({
                'message': 'No more lessons.',
                'completed': True
            })

        if lesson_order[next_lesson.pk] <= lesson_order[lesson_id]:
            return Response({'message': 'No unlocked required lesson follows this lesson.', 'completed': False})

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
            status__in=ACCESS_STATUSES
        )
        require_unlocked_lesson(enrollment, lesson)

        # Watch time is required only for videos the learn page can actually
        # play and observe (LRN-02); otherwise a lesson with a non-trackable
        # link could never be completed.
        from courses.video import parse_video_url
        requires_watch_time = (
            lesson.content_type == 'video'
            and lesson.duration_seconds > 0
            and parse_video_url(lesson.video_url) is not None
        )
        if requires_watch_time:
            progress = enrollment.lesson_progress.filter(lesson=lesson).first()
            if progress is None or not auto_complete_lesson(progress):
                return Response(
                    {'error': 'Watch at least 80% of the video to complete this lesson.',
                     'code': 'watch_threshold_not_met'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        if not is_lesson_assessment_completed(request.user, lesson):
            return Response(
                {'error': 'Lesson assessment requirements have not been met.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        progress = mark_lesson_completed(enrollment, lesson, local_zone=learning_timezone(request))
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
    serializer_class = EnrollmentStatsSerializer

    def get(self, request):
        user = request.user
        enrollments = Enrollment.objects.filter(user=user)

        stats = enrollments.aggregate(
            total_enrollments=Count('pk'),
            active_enrollments=Count('pk', filter=Q(status='active')),
            completed_enrollments=Count('pk', filter=Q(status='completed')),
            canceled_enrollments=Count('pk', filter=Q(status='canceled')),
            total_courses_enrolled=Count('course_id', distinct=True),
        )
        active_courses = with_enrollment_progress(enrollments.filter(status='active')).values_list(
            'required_completed_count', 'required_count',
        )
        active_progress = [lesson_progress_percentage(completed, total) for completed, total in active_courses]
        stats['average_progress'] = round(sum(active_progress) / len(active_progress), 2) if active_progress else 0
        
        # Calculate total watch time in hours
        total_watch_time = LessonProgress.objects.filter(
            user=user
        ).aggregate(total=Sum('watch_time'))['total'] or 0
        stats['total_watch_time_hours'] = round(total_watch_time / 3600, 2)

        serializer = EnrollmentStatsSerializer(stats)
        return Response(serializer.data)


class LearningProgressDashboardView(generics.ListAPIView):
    """Get detailed progress for all enrolled courses."""
    permission_classes = [IsAuthenticated]
    serializer_class = CourseProgressStatsSerializer

    def get_queryset(self):
        queryset = Enrollment.objects.filter(user=self.request.user, status='active').select_related('course')
        return with_enrollment_progress(queryset.order_by('-enrolled_at', '-pk'), durations=True)


# ===========================
# 👨‍🏫 Instructor Analytics (CSV Export)
# ===========================

# Characters that make spreadsheet apps treat a cell as a formula (CSV/formula
# injection). Lesson titles are instructor-authored, so neutralise them.
_CSV_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def _csv_safe(value):
    text = '' if value is None else str(value)
    return "'" + text if text.startswith(_CSV_FORMULA_PREFIXES) else text


class InstructorLessonAnalyticsCSVView(APIView):
    """Export per-lesson started/completed/drop-off counts as CSV (course owner or admin).

    BUG-01: this used to annotate Count('lessonprogress') (the relation is
    `lesson_progress`, so every request raised FieldError) and divided by the
    started count in SQL (division by zero on Postgres for unstarted lessons).
    """
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        from courses.policies import can_manage_course

        course = get_object_or_404(Course, id=course_id)
        if not can_manage_course(request.user, course):
            return Response({'error': 'Course not found.'}, status=status.HTTP_404_NOT_FOUND)

        lessons = (
            Lesson.objects.filter(module__course=course)
            .annotate(
                started_count=Count('lesson_progress', distinct=True),
                completed_count=Count(
                    'lesson_progress', filter=Q(lesson_progress__is_completed=True), distinct=True
                ),
            )
            .order_by('module__position', 'module__id', 'position', 'id')
        )

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="lesson_analytics_course_{int(course.id)}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Lesson ID', 'Lesson Title', 'Started Enrollments',
            'Completed Enrollments', 'Drop-off Count', 'Drop-off Rate (%)'
        ])
        for lesson in lessons:
            started, completed = lesson.started_count, lesson.completed_count
            drop_off = started - completed
            rate = round(drop_off * 100.0 / started, 2) if started else 0.0
            writer.writerow([lesson.id, _csv_safe(lesson.title), started, completed, drop_off, rate])

        return response
