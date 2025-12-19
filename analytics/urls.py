from django.urls import path
from .views import InstructorCourseAnalyticsView

urlpatterns = [
    path('instructor/course/<int:course_id>/analytics/', InstructorCourseAnalyticsView.as_view(), name='instructor-course-analytics'),
]
