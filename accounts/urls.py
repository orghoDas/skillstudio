from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views
from .views import InstructorOnlyView

urlpatterns = [
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/register/", views.RegisterView.as_view(), name="api_register"),
    path("instructor-only/", InstructorOnlyView.as_view(), name="instructor_only"),
    path("promote/<int:user_id>/", views.PromoteToInstructorView.as_view(), name="promote_to_instructor"),
    path("login/", views.login_page, name="login"),
    path("register/", views.register_page, name="register"),
    path("me/", views.MeView.as_view(), name="me"),
]
