from collections.abc import Mapping

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

from .serializers import (
    RegisterSerializer, AccountProfileSerializer, MeSerializer,
    ChangePasswordSerializer,
    APIKeySerializer, CreateAPIKeySerializer, UserSerializer,
    UpdateUserRoleSerializer, UnifiedProfileSerializer,
)
from .models import Profile, User, APIKey
from .authentication import enforce_cookie_csrf
from .cookies import clear_jwt_cookies, get_refresh_cookie
from .permissions import IsInstructor, IsAdmin


def _blacklist_user_refresh_tokens(user):
    """Blacklist every outstanding refresh token for a user.

    Forces re-authentication after a sensitive account change. Access tokens
    already issued remain valid until they expire (SIMPLE_JWT access lifetime).
    """
    for outstanding in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=outstanding)


class RegisterView(generics.CreateAPIView):
    """Register a new user account"""
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)
    throttle_scope = "register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            "message": "User registered successfully.",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role
            }
        }, status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    """Log out: blacklist the refresh token (from body or cookie) and clear the
    auth cookies. Succeeds even without a token so clients can always log out."""
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(responses={205: OpenApiTypes.OBJECT})
    def post(self, request):
        cookie_refresh = get_refresh_cookie(request)
        if cookie_refresh or request.COOKIES.get(settings.JWT_AUTH_COOKIE):
            enforce_cookie_csrf(request)

        data = request.data
        body_refresh = data.get('refresh') if isinstance(data, Mapping) else None
        tokens = (body_refresh, cookie_refresh)
        for refresh in {value for value in tokens if isinstance(value, str) and value}:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # already invalid/blacklisted — clearing cookies still logs out

        response = Response({"message": "Logged out."}, status=status.HTTP_205_RESET_CONTENT)
        return clear_jwt_cookies(response)


class ChangePasswordView(APIView):
    """Change password for authenticated user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        # Check old password
        if not user.check_password(serializer.validated_data['old_password']):
            return Response({
                "old_password": ["Old password is incorrect."]
            }, status=status.HTTP_400_BAD_REQUEST)

        # Set new password
        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password'])

        # Invalidate outstanding refresh tokens so other sessions can't continue.
        _blacklist_user_refresh_tokens(user)

        return Response({
            "message": "Password changed successfully. Please log in again."
        }, status=status.HTTP_200_OK)


@extend_schema_view(
    put=extend_schema(request=AccountProfileSerializer, responses=UnifiedProfileSerializer),
    patch=extend_schema(request=AccountProfileSerializer, responses=UnifiedProfileSerializer),
)
class ProfileView(APIView):
    """Get and update the stable current-user profile envelope."""
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = UnifiedProfileSerializer

    def get(self, request):
        serializer = UnifiedProfileSerializer(request.user)
        return Response(serializer.data)
    
    def put(self, request):
        profile, _ = Profile.objects.get_or_create(user=request.user)
        serializer = AccountProfileSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UnifiedProfileSerializer(request.user).data)
    
    def patch(self, request):
        return self.put(request)


class MeView(APIView):
    """Get and update current user information"""
    permission_classes = [IsAuthenticated]
    serializer_class = MeSerializer

    def get(self, request):
        # request.user is loaded fresh from the database on every request.
        return Response(MeSerializer(request.user).data)

    def patch(self, request):
        serializer = MeSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserListView(generics.ListAPIView):
    """List all users (admin only)"""
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all().select_related('profile')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        return queryset


class UserDetailView(generics.RetrieveAPIView):
    """Get user details (admin only)"""
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all().select_related('profile')
    lookup_field = 'id'


@transaction.atomic
def _update_role(user_id, role):
    user = get_object_or_404(User.objects.select_for_update(), id=user_id)
    if user.is_superuser and role != User.Role.ADMIN:
        raise ValidationError({'role': 'A superuser must retain the admin role.'})
    user.role = role
    user.save(update_fields=['role'])
    return user


class UpdateUserRoleView(APIView):
    """Update user role (admin only)"""
    permission_classes = [IsAdmin]

    def patch(self, request, user_id):
        serializer = UpdateUserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = _update_role(user_id, serializer.validated_data['role'])
        
        return Response({
            "message": f"User {user.email} role updated to {user.role}.",
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class PromoteToInstructorView(APIView):
    """Promote user to instructor (admin only)"""
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = _update_role(user_id, User.Role.INSTRUCTOR)
        return Response({
            "message": f"User {user.email} promoted to Instructor.",
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class DeactivateUserView(APIView):
    """Deactivate user account (admin only)"""
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response({
            "message": f"User {user.email} has been deactivated."
        }, status=status.HTTP_200_OK)


class ActivateUserView(APIView):
    """Activate user account (admin only)"""
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.is_active = True
        user.save(update_fields=['is_active'])
        return Response({
            "message": f"User {user.email} has been activated."
        }, status=status.HTTP_200_OK)


class APIKeyListCreateView(generics.ListCreateAPIView):
    """List and create API keys for authenticated user"""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateAPIKeySerializer
        return APIKeySerializer
    
    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = CreateAPIKeySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        scopes = serializer.validated_data.get('scopes', [])
        parent = request.auth
        if isinstance(parent, APIKey) and parent.scopes:
            requested = set(scopes or APIKey.Scope.values)
            if not requested.issubset(parent.scopes):
                raise PermissionDenied("An API key cannot create a key with broader scopes.")
        api_key, secret = APIKey.create_for_user(
            user=request.user,
            label=serializer.validated_data["label"],
            scopes=scopes,
        )
        data = APIKeySerializer(api_key).data
        data["key"] = secret
        return Response(data, status=status.HTTP_201_CREATED)


class APIKeyDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete API key"""
    serializer_class = APIKeySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user).order_by('-created_at')


class APIKeyToggleView(APIView):
    """Toggle API key active status"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, key_id):
        api_key = get_object_or_404(APIKey, id=key_id, user=request.user)
        if api_key.is_active:
            api_key.revoke()
        else:
            api_key.restore()
        
        return Response({
            "message": f"API key {'activated' if api_key.is_active else 'deactivated'}.",
            "api_key": APIKeySerializer(api_key).data
        }, status=status.HTTP_200_OK)


class InstructorOnlyView(APIView):
    """Test endpoint for instructor-only access"""
    permission_classes = [IsInstructor]

    def get(self, request):
        return Response({
            "message": "Hello, Instructor!",
            'user': request.user.email
        })
