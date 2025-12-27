from django.urls import path

from .views import InstructorDashboardView, LessonProgressView, LessonWatchTimeView, ResumeLessonView, CourseProgressView, InstructorCourseComparisonView

urlpatterns = [
    path('lessons/<int:lesson_id>/progress/', LessonProgressView.as_view(), name='lesson-progress'),
    path('lessons/<int:lesson_id>/watch-time/', LessonWatchTimeView.as_view(), name='lesson-watch-time'),
    path('courses/<int:course_id>/resume-lesson/', ResumeLessonView.as_view(), name='resume-lesson'),
    path('courses/<int:course_id>/progress/', CourseProgressView.as_view(), name='course-progress'),
    path('instructor/dashboard/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
    path('instructor/courses/<int:course_id>/analytics/', InstructorCourseComparisonView.as_view(), name='instructor-course-analytics'),
]
