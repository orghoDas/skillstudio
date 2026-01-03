"""Course Analytics Views

NOTE: This module previously contained duplicate analytics views.
They have been consolidated as follows:

- InstructorDashboardView -> Use instructors.views.InstructorDashboardView
- CourseAnalyticsView -> Use analytics.views.InstructorCourseAnalyticsView
- AdminCourseStatsView -> Kept here as it's course-specific admin view

For backward compatibility, we import and re-export the proper views below.
"""

from django.db.models import Count, Avg, Sum, Q, F
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsInstructor, IsAdmin
from .models import Course, Lesson
from social.models import Review
from enrollments.models import Enrollment, LessonProgress

# Import from proper locations
from instructors.views import InstructorDashboardView  # Main instructor dashboard
from analytics.views import InstructorCourseAnalyticsView as CourseAnalyticsView  # Course analytics

# Only keep admin stats here as it's course-specific
class AdminCourseStatsView(APIView):
    """Platform-wide course statistics (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        # Overall course stats
        course_stats = Course.objects.aggregate(
            total_courses=Count('id'),
            published=Count('id', filter=Q(status='published')),
            under_review=Count('id', filter=Q(status='under_review')),
            draft=Count('id', filter=Q(status='draft')),
        )

        # Enrollment stats
        enrollment_stats = Enrollment.objects.aggregate(
            total_enrollments=Count('id'),
            active=Count('id', filter=Q(status='active')),
            completed=Count('id', filter=Q(status='completed'))
        )

        # Revenue stats
        total_revenue = Enrollment.objects.filter(
            status__in=['active', 'completed']
        ).aggregate(revenue=Sum('amount_paid'))['revenue'] or 0

        # Top courses by enrollment
        top_courses = Course.objects.filter(
            status='published'
        ).annotate(
            enrollment_count=Count('enrollments', filter=Q(enrollments__status='active'))
        ).order_by('-enrollment_count')[:10]

        top_courses_data = [{
            'id': c.id,
            'title': c.title,
            'instructor': c.instructor.email,
            'enrollments': c.enrollment_count
        } for c in top_courses]

        # Courses pending review
        pending_review = Course.objects.filter(
            status='under_review'
        ).select_related('instructor').order_by('submitted_for_review_at')

        pending_data = [{
            'id': c.id,
            'title': c.title,
            'instructor': c.instructor.email,
            'submitted_at': c.submitted_for_review_at
        } for c in pending_review]

        return Response({
            'courses': course_stats,
            'enrollments': enrollment_stats,
            'total_revenue': float(total_revenue),
            'top_courses': top_courses_data,
            'courses_pending_review': pending_data
        })
