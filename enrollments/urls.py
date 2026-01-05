from django.urls import path

from .views import (
    # Enrollment Management
    EnrollmentListView,
    EnrollmentDetailView,
    EnrollCourseView,
    CancelEnrollmentView,
    MyLearningView,
    CompletedCoursesView,
    # Progress Tracking
    CourseProgressView,
    LessonProgressView,
    LessonWatchTimeView,
    ResumeLessonView,
    NextLessonView,
    CompleteLessonView,
    # Wishlist
    WishlistListView,
    AddToWishlistView,
    RemoveFromWishlistView,
    CheckWishlistView,
    # Statistics & Analytics
    EnrollmentStatsView,
    LearningProgressDashboardView,
    InstructorLessonAnalyticsCSVView,
)

# Analytics app removed
from instructors.views import InstructorDashboardView
# InstructorCourseComparisonView and InstructorLessonDropoffView removed with analytics app


urlpatterns = [
    # ===========================
    # 🎓 Enrollment Management
    # ===========================
    path('', EnrollmentListView.as_view(), name='enrollment-list-root'),
    path('my-enrollments/', EnrollmentListView.as_view(), name='enrollment-list'),
    path('enrollments/<int:pk>/', EnrollmentDetailView.as_view(), name='enrollment-detail'),
    path('enroll/', EnrollCourseView.as_view(), name='enroll-course'),
    path('enrollments/<int:enrollment_id>/cancel/', CancelEnrollmentView.as_view(), name='cancel-enrollment'),
    path('my-learning/', MyLearningView.as_view(), name='my-learning'),
    path('completed-courses/', CompletedCoursesView.as_view(), name='completed-courses'),
    
    # ===========================
    # 📊 Progress Tracking
    # ===========================
    path('courses/<int:course_id>/progress/', CourseProgressView.as_view(), name='course-progress'),
    path('lessons/<int:lesson_id>/progress/', LessonProgressView.as_view(), name='lesson-progress'),
    path('lessons/<int:lesson_id>/watch-time/', LessonWatchTimeView.as_view(), name='lesson-watch-time'),
    path('courses/<int:course_id>/resume-lesson/', ResumeLessonView.as_view(), name='resume-lesson'),
    path('courses/<int:course_id>/lessons/<int:lesson_id>/next/', NextLessonView.as_view(), name='next-lesson'),
    path('lessons/<int:lesson_id>/complete/', CompleteLessonView.as_view(), name='complete-lesson'),
    
    # ===========================
    # 📋 Wishlist Management
    # ===========================
    path('wishlist/', WishlistListView.as_view(), name='wishlist-list'),
    path('wishlist/add/', AddToWishlistView.as_view(), name='wishlist-add'),
    path('wishlist/<int:pk>/remove/', RemoveFromWishlistView.as_view(), name='wishlist-remove'),
    path('wishlist/check/<int:course_id>/', CheckWishlistView.as_view(), name='wishlist-check'),
    
    # ===========================
    # 📊 Statistics & Analytics
    # ===========================
    path('stats/', EnrollmentStatsView.as_view(), name='enrollment-stats'),
    path('learning-dashboard/', LearningProgressDashboardView.as_view(), name='learning-dashboard'),
    
    # ===========================
    # 👨‍🏫 Instructor Analytics (analytics app removed)
    # ===========================
    path('instructor/dashboard/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
    # path('instructor/courses/<int:course_id>/analytics/', InstructorCourseComparisonView.as_view(), name='instructor-course-analytics'),
    # path('instructor/courses/<int:course_id>/lesson-dropoff/', InstructorLessonDropoffView.as_view(), name='instructor-lesson-dropoff'),
    path('instructor/courses/<int:course_id>/lesson-analytics-csv/', InstructorLessonAnalyticsCSVView.as_view(), name='instructor-lesson-analytics-csv'),
]

