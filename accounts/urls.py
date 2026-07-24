from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from .custom_token import CustomTokenObtainPairView
from . import views

urlpatterns = [
    # JWT Authentication
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    
    # Registration
    path("register/", views.RegisterView.as_view(), name="api_register"),
    path("logout/", views.LogoutView.as_view(), name="logout"),

    # Password Management
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    
    # Current User
    path("me/", views.MeView.as_view(), name="me"),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    
    # User Management (Admin)
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/<int:id>/", views.UserDetailView.as_view(), name="user_detail"),
    path("users/<int:user_id>/role/", views.UpdateUserRoleView.as_view(), name="update_user_role"),
    path("users/<int:user_id>/promote/", views.PromoteToInstructorView.as_view(), name="promote_to_instructor"),
    path("users/<int:user_id>/deactivate/", views.DeactivateUserView.as_view(), name="deactivate_user"),
    path("users/<int:user_id>/activate/", views.ActivateUserView.as_view(), name="activate_user"),
    
    # API Keys
    path("api-keys/", views.APIKeyListCreateView.as_view(), name="api_key_list_create"),
    path("api-keys/<int:id>/", views.APIKeyDetailView.as_view(), name="api_key_detail"),
    path("api-keys/<int:key_id>/toggle/", views.APIKeyToggleView.as_view(), name="api_key_toggle"),
    
    # Test endpoints
    path("instructor-only/", views.InstructorOnlyView.as_view(), name="instructor_only"),
]
