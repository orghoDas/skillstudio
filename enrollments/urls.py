from django.urls import path
from .views import LessonProgressView, LessonWatchTimeView

urlpatterns = [
    path('lessons/<int:lesson_id>/progress/', LessonProgressView.as_view(), name='lesson-progress'),
    path('lessons/<int:lesson_id>/watch-time/', LessonWatchTimeView.as_view(), name='lesson-watch-time'),
]
