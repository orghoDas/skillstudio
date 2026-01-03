from django.urls import path
from .views import (
    # Instructor analytics
    InstructorCourseAnalyticsView, 
    InstructorCourseComparisonView, 
    InstructorLessonDropoffView,
    InstructorDashboardAnalyticsView,
    InstructorEarningsView,
    LessonAnalyticsView,
    # Student analytics
    StudentAnalyticsView,
    StudentProgressReportView,
    # Event analytics
    EventAnalyticsView,
    # Platform analytics
    PlatformAnalyticsView,
    TrendingCoursesView,
    SearchAnalyticsView,
    # Public analytics
    PublicCourseStatsView,
    # Tracking
    TrackInteractionView,
)

app_name = 'analytics'

urlpatterns = [
    # Instructor Analytics
    path('instructor/dashboard/', InstructorDashboardAnalyticsView.as_view(), name='instructor-dashboard'),
    path('instructor/course/<int:course_id>/', InstructorCourseAnalyticsView.as_view(), name='instructor-course-analytics'),
    path('instructor/courses/comparison/', InstructorCourseComparisonView.as_view(), name='instructor-courses-comparison'),
    path('instructor/course/<int:course_id>/dropoff/', InstructorLessonDropoffView.as_view(), name='instructor-lesson-dropoff'),
    path('instructor/earnings/', InstructorEarningsView.as_view(), name='instructor-earnings'),
    path('instructor/lesson/<int:lesson_id>/', LessonAnalyticsView.as_view(), name='lesson-analytics'),
    
    # Student Analytics
    path('student/dashboard/', StudentAnalyticsView.as_view(), name='student-analytics'),
    path('student/course/<int:course_id>/progress/', StudentProgressReportView.as_view(), name='student-progress'),
    
    # Event Analytics
    path('event/<int:event_id>/', EventAnalyticsView.as_view(), name='event-analytics'),
    
    # Platform Analytics (Admin)
    path('platform/', PlatformAnalyticsView.as_view(), name='platform-analytics'),
    path('trending/', TrendingCoursesView.as_view(), name='trending-courses'),
    path('search/', SearchAnalyticsView.as_view(), name='search-analytics'),
    
    # Public Analytics
    path('public/course/<int:course_id>/', PublicCourseStatsView.as_view(), name='public-course-stats'),
    
    # Interaction Tracking
    path('track/', TrackInteractionView.as_view(), name='track-interaction'),
]

