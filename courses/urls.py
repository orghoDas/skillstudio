from django.urls import path
from .views import CourseCurriculumView, LessonDetailView

urlpatterns = [
    path('lessons/<int:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),
    path('<int:course_id>/curriculum/', CourseCurriculumView.as_view(), name='course-curriculum'),
]