"""Admin-only, platform-wide course statistics (/api/courses/admin/course-stats/).

Instructor analytics live in instructors.views (InstructorDashboardView).
"""

from django.db.models import Count, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import IsAdmin
from .models import Course
from .services import course_learner_count
from enrollments.models import Enrollment
from payments.services import get_payment_stats

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
        total_revenue = get_payment_stats()['total_revenue']

        top_courses = (
            Course.objects.filter(status='published').select_related('instructor')
            .annotate(enrollment_count=course_learner_count())
            .order_by('-enrollment_count', '-pk')[:10]
        )

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
            'total_revenue': format(total_revenue, '.2f'),
            'top_courses': top_courses_data,
            'courses_pending_review': pending_data
        })
