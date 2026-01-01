from django.urls import path
from .views import InstructorDashboardView

urlpatterns = [
    path('instructor/dashboard/', InstructorDashboardView.as_view(), name='instructor-dashboard'),
]

