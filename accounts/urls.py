from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views

urlpatterns = [
    # JWT Authentication
    path("api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    
    # Registration & Email Verification
    path("api/register/", views.RegisterView.as_view(), name="api_register"),
    path("api/verify-email/", views.EmailVerificationView.as_view(), name="verify_email"),
    path("api/resend-verification/", views.ResendVerificationEmailView.as_view(), name="resend_verification"),
    
    # Password Management
    path("api/password-reset/", views.PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("api/password-reset/confirm/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("api/change-password/", views.ChangePasswordView.as_view(), name="change_password"),
    
    # Current User
    path("api/me/", views.MeView.as_view(), name="me"),
    path("api/profile/", views.ProfileView.as_view(), name="profile"),
    
    # User Management (Admin)
    path("api/users/", views.UserListView.as_view(), name="user_list"),
    path("api/users/<int:id>/", views.UserDetailView.as_view(), name="user_detail"),
    path("api/users/<int:user_id>/role/", views.UpdateUserRoleView.as_view(), name="update_user_role"),
    path("api/users/<int:user_id>/promote/", views.PromoteToInstructorView.as_view(), name="promote_to_instructor"),
    path("api/users/<int:user_id>/deactivate/", views.DeactivateUserView.as_view(), name="deactivate_user"),
    path("api/users/<int:user_id>/activate/", views.ActivateUserView.as_view(), name="activate_user"),
    
    # API Keys
    path("api/api-keys/", views.APIKeyListCreateView.as_view(), name="api_key_list_create"),
    path("api/api-keys/<int:id>/", views.APIKeyDetailView.as_view(), name="api_key_detail"),
    path("api/api-keys/<int:key_id>/toggle/", views.APIKeyToggleView.as_view(), name="api_key_toggle"),
    
    # Test endpoints
    path("api/instructor-only/", views.InstructorOnlyView.as_view(), name="instructor_only"),
]
