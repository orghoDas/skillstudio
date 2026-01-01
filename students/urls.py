from django.urls import path
from .views import StudentDashboardView, StudentActivityFeedView

urlpatterns = [
    path('dashboard/', StudentDashboardView.as_view(), name='student-dashboard'),
    path('activity-feed/', StudentActivityFeedView.as_view(), name='student-activity-feed'),
]
