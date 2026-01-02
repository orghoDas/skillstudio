from django.urls import path
from .views import (
    InstructorDashboardView,
    InstructorCourseDetailView
)

urlpatterns = [
    path("dashboard/", InstructorDashboardView.as_view()),
    path("courses/<int:course_id>/", InstructorCourseDetailView.as_view()),
]
