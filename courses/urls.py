from django.urls import path
from .views import CourseCurriculumView, LessonDetailView, PublishCourseView, RejectCourseView, ResumeLearningView, SubmitCourseForReviewView

urlpatterns = [
    path('lessons/<int:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('<int:course_id>/curriculum/', CourseCurriculumView.as_view(), name='course-curriculum'),
    path('courses/<int:course_id>/submit/', SubmitCourseForReviewView.as_view(), name='submit-course'),
    path('courses/<int:course_id>/publish/', PublishCourseView.as_view(), name='publish-course'),
    path('courses/<int:course_id>/reject/', RejectCourseView.as_view(), name='reject-course'),
    path('courses/<int:course_id>/resume/', ResumeLearningView.as_view(), name='resume-learning'),
]