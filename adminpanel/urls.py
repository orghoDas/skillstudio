from django.urls import path
from adminpanel.views import AdminDashboardView

urlpatterns = [
    path("dashboard/", AdminDashboardView.as_view()),
]
