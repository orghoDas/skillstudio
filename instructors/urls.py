from django.urls import path
from .views import (
    InstructorDashboardView,
    InstructorProfileView,
    InstructorPayoutListView,
    InstructorPayoutRequestView,
    InstructorStudentsView,
)
from analytics.views import InstructorLessonDropoffView

urlpatterns = [
    path("dashboard/", InstructorDashboardView.as_view(), name="instructor-dashboard"),
    path("profile/", InstructorProfileView.as_view(), name="instructor-profile"),
    path("students/", InstructorStudentsView.as_view(), name="instructor-students"),
    path("payouts/", InstructorPayoutListView.as_view(), name="instructor-payouts"),
    path("payouts/request/", InstructorPayoutRequestView.as_view(), name="instructor-payout-request"),
    # Course detail with dropoff moved to analytics
    path("courses/<int:course_id>/dropoff/", InstructorLessonDropoffView.as_view(), name="instructor-course-dropoff"),
]
