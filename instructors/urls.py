from django.urls import path
from .views import (
    InstructorDashboardView,
    InstructorProfileView,
    InstructorPayoutListView,
    InstructorPayoutRequestView,
    InstructorStudentsView,
)
# Analytics app removed - InstructorLessonDropoffView no longer available

urlpatterns = [
    path("dashboard/", InstructorDashboardView.as_view(), name="instructor-dashboard"),
    path("stats/", InstructorDashboardView.as_view(), name="instructor-stats"),  # Alias for dashboard
    path("profile/", InstructorProfileView.as_view(), name="instructor-profile"),
    path("students/", InstructorStudentsView.as_view(), name="instructor-students"),
    path("payouts/", InstructorPayoutListView.as_view(), name="instructor-payouts"),
    path("payouts/request/", InstructorPayoutRequestView.as_view(), name="instructor-payout-request"),
    # Analytics app removed - dropoff endpoint disabled
    # path("courses/<int:course_id>/dropoff/", InstructorLessonDropoffView.as_view(), name="instructor-course-dropoff"),
]
