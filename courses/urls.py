from django.urls import path
from .views import LessonDetailView

urlpatterns = [
    path('lessons/<int:lesson_id>/', LessonDetailView.as_view(), name='lesson-detail'),
]