from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta

from courses.models import Course
from accounts.permissions import IsInstructor, IsAdmin
from analytics.services import (
    # Course analytics
    get_course_analytics, get_lesson_analytics, get_course_comparison, get_lesson_dropoff_analysis,
    # Instructor analytics
    get_instructor_analytics, get_instructor_earnings_breakdown,
    # Student analytics
    get_student_analytics, get_student_progress_report,
    # Event analytics
    get_event_analytics,
    # Platform analytics
    get_platform_overview, get_trending_courses, get_search_analytics,
    # Tracking
    track_user_interaction,
)


# ==========================================
# INSTRUCTOR ANALYTICS VIEWS
# ==========================================

class InstructorCourseAnalyticsView(APIView):
    """Get comprehensive analytics for a specific course (instructor only)"""
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        instructor = request.user
        
        analytics = get_course_analytics(course_id, instructor=instructor)
        
        if analytics is None:
            return Response(
                {"error": "Course not found or you don't have permission to view it"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(analytics)


class InstructorCourseComparisonView(APIView):
    """Compare analytics across all instructor courses"""
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user
        comparison_data = get_course_comparison(instructor)
        
        return Response({
            'total_courses': len(comparison_data),
            'courses': comparison_data,
        })


class InstructorLessonDropoffView(APIView):
    """Analyze lesson-level drop-off rates for a course"""
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, course_id):
        instructor = request.user
        
        dropoff_data = get_lesson_dropoff_analysis(course_id, instructor=instructor)
        
        if dropoff_data is None:
            return Response(
                {"error": "Course not found or you don't have permission to view it"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'course_id': course_id,
            'lessons': dropoff_data,
        })


class InstructorDashboardAnalyticsView(APIView):
    """Complete instructor analytics dashboard"""
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user
        analytics = get_instructor_analytics(instructor)
        
        # Get earnings breakdown for last 12 months
        start_date = datetime.now() - timedelta(days=365)
        earnings = get_instructor_earnings_breakdown(
            instructor,
            start_date=start_date
        )
        
        return Response({
            'overview': analytics,
            'earnings': earnings,
        })


class InstructorEarningsView(APIView):
    """Detailed earnings breakdown for instructor"""
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request):
        instructor = request.user
        
        # Get date range from query params
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        
        earnings = get_instructor_earnings_breakdown(
            instructor,
            start_date=start_date,
            end_date=end_date
        )
        
        return Response(earnings)


class LessonAnalyticsView(APIView):
    """Get analytics for a specific lesson"""
    permission_classes = [IsAuthenticated, IsInstructor]

    def get(self, request, lesson_id):
        analytics = get_lesson_analytics(lesson_id)
        
        if analytics is None:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(analytics)


# ==========================================
# STUDENT ANALYTICS VIEWS
# ==========================================

class StudentAnalyticsView(APIView):
    """Get analytics for the current student"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = request.user
        analytics = get_student_analytics(student)
        
        return Response(analytics)


class StudentProgressReportView(APIView):
    """Get detailed progress report for a student in a specific course"""
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        student = request.user
        
        progress = get_student_progress_report(student, course_id)
        
        if progress is None:
            return Response(
                {"error": "Enrollment not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(progress)


# ==========================================
# EVENT ANALYTICS VIEWS
# ==========================================

class EventAnalyticsView(APIView):
    """Get analytics for a specific event"""
    permission_classes = [IsAuthenticated]

    def get(self, request, event_id):
        analytics = get_event_analytics(event_id)
        
        if analytics is None:
            return Response(
                {"error": "Event not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response(analytics)


# ==========================================
# PLATFORM-WIDE ANALYTICS (Admin)
# ==========================================

class PlatformAnalyticsView(APIView):
    """Platform-wide analytics overview (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        
        overview = get_platform_overview(days=days)
        trending = get_trending_courses(limit=10, days=7)
        search_analytics = get_search_analytics(days=days)
        
        return Response({
            'overview': overview,
            'trending_courses': trending,
            'search_analytics': search_analytics,
        })


class TrendingCoursesView(APIView):
    """Get trending courses"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get('limit', 10))
        days = int(request.query_params.get('days', 7))
        
        trending = get_trending_courses(limit=limit, days=days)
        
        return Response({
            'trending_courses': trending,
            'period_days': days,
        })


class SearchAnalyticsView(APIView):
    """Get search analytics (admin only)"""
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        
        analytics = get_search_analytics(days=days)
        
        return Response(analytics)


# ==========================================
# PUBLIC COURSE ANALYTICS
# ==========================================

class PublicCourseStatsView(APIView):
    """Public-facing course statistics (no authentication required)"""
    
    def get(self, request, course_id):
        # Get basic, non-sensitive course analytics
        analytics = get_course_analytics(course_id)
        
        if analytics is None:
            return Response(
                {"error": "Course not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Return only public-safe data
        public_data = {
            'course_id': analytics['course_id'],
            'total_enrollments': analytics['total_enrollments'],
            'average_rating': analytics['average_rating'],
            'total_reviews': analytics['total_reviews'],
            'completion_rate': analytics['completion_rate'],
        }
        
        return Response(public_data)


# ==========================================
# USER INTERACTION TRACKING
# ==========================================

class TrackInteractionView(APIView):
    """Track user interactions for analytics"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        action = request.data.get('action')
        
        if not action:
            return Response(
                {"error": "Action is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Extract metadata
        course_id = request.data.get('course_id')
        event_id = request.data.get('event_id')
        metadata = request.data.get('metadata', {})
        
        # Get course/event objects if provided
        from courses.models import Course
        from events.models import Event
        
        course = Course.objects.filter(id=course_id).first() if course_id else None
        event = Event.objects.filter(id=event_id).first() if event_id else None
        
        # Track interaction
        interaction = track_user_interaction(
            user=user,
            action=action,
            course=course,
            event=event,
            metadata=metadata,
            session_id=request.data.get('session_id', ''),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        
        return Response({
            'status': 'tracked',
            'interaction_id': interaction.id,
        }, status=status.HTTP_201_CREATED)

