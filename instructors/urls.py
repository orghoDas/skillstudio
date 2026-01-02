from django.urls import path
from .views import InstructorDashboardView, InstructorEnrollmentTrendsView, InstructorCourseAnalyticsView, InstructorCourseDropoffView, InstructorRevenueView

urlpatterns = [
    path('instructor/dashboard/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
    path('instructor/enrollment-trends/', InstructorEnrollmentTrendsView.as_view(), name='instructor-enrollment-trends'),
    path('instructor/courses/<int:course_id>/analytics/', InstructorCourseAnalyticsView.as_view(), name='instructor-course-analytics'),
    path('instructor/courses/<int:course_id>/lesson-dropoff/', InstructorCourseDropoffView.as_view(), name='instructor-course-lesson-dropoff'),
    path('instructor/revenue/', InstructorRevenueView.as_view(), name='instructor-revenue'),
]

