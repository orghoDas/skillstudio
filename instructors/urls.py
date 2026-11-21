from django.urls import path
from .views import (
    InstructorDashboardView,
    InstructorProfileView,
    InstructorStudentsView,
    FeaturedInstructorsView,
)
# Analytics app removed - InstructorLessonDropoffView no longer available

urlpatterns = [
    path("dashboard/", InstructorDashboardView.as_view(), name="instructor-dashboard"),
    path("stats/", InstructorDashboardView.as_view(), name="instructor-stats"),  # Alias for dashboard
    path("profile/", InstructorProfileView.as_view(), name="instructor-profile"),
    path("students/", InstructorStudentsView.as_view(), name="instructor-students"),
    path("featured/", FeaturedInstructorsView.as_view(), name="instructors-featured"),
    # Payouts moved to /api/payments/payouts/ (wallet-based, PAY-07).
    # Analytics app removed - dropoff endpoint disabled
    # path("courses/<int:course_id>/dropoff/", InstructorLessonDropoffView.as_view(), name="instructor-course-dropoff"),
]
