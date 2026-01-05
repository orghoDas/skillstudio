from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from .serializers import (
    RegisterSerializer, ProfileSerializer, MeSerializer,
    ChangePasswordSerializer, PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer, EmailVerificationSerializer,
    APIKeySerializer, CreateAPIKeySerializer, UserSerializer,
    UpdateUserRoleSerializer
)
from .models import Profile, User, EmailVerificationToken, PasswordResetToken, APIKey
from .permissions import IsInstructor, IsAdmin
from datetime import timedelta


class RegisterView(generics.CreateAPIView):
    """Register a new user account"""
    serializer_class = RegisterSerializer
    permission_classes = (permissions.AllowAny,)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response({
            "message": "User registered successfully. Please check your email for verification.",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "role": user.role
            }
        }, status=status.HTTP_201_CREATED)


class EmailVerificationView(APIView):
    """Verify user email with token"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token_value = serializer.validated_data['token']
        
        try:
            token = EmailVerificationToken.objects.get(
                token=token_value,
                is_used=False,
                expires_at__gt=timezone.now()
            )
            
            user = token.user
            user.is_active = True
            user.save()
            
            token.is_used = True
            token.save()
            
            return Response({
                "message": "Email verified successfully."
            }, status=status.HTTP_200_OK)
            
        except EmailVerificationToken.DoesNotExist:
            return Response({
                "error": "Invalid or expired verification token."
            }, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationEmailView(APIView):
    """Resend email verification token"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        if user.is_active:
            return Response({
                "message": "Email is already verified."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Invalidate old tokens
        EmailVerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)
        
        # Create new token
        token = EmailVerificationToken.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # TODO: Send email with token
        
        return Response({
            "message": "Verification email sent successfully."
        }, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    """Request password reset - sends reset token to email"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            
            # Create password reset token
            token = PasswordResetToken.objects.create(
                user=user,
                expires_at=timezone.now() + timedelta(hours=24)
            )
            
            # TODO: Send email with token
            
            return Response({
                "message": "Password reset email sent successfully."
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            # Don't reveal if user exists
            return Response({
                "message": "Password reset email sent successfully."
            }, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    """Confirm password reset with token and new password"""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        token_value = serializer.validated_data['token']
        new_password = serializer.validated_data['new_password']
        
        try:
            token = PasswordResetToken.objects.get(
                token=token_value,
                expires_at__gt=timezone.now()
            )
            
            user = token.user
            user.set_password(new_password)
            user.save()
            
            # Delete the used token
            token.delete()
            
            # Delete all other reset tokens for this user
            PasswordResetToken.objects.filter(user=user).delete()
            
            return Response({
                "message": "Password reset successfully."
            }, status=status.HTTP_200_OK)
            
        except PasswordResetToken.DoesNotExist:
            return Response({
                "error": "Invalid or expired reset token."
            }, status=status.HTTP_400_BAD_REQUEST)


class ChangePasswordView(APIView):
    """Change password for authenticated user"""
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
        user.save()
        
        return Response({
            "message": "Password changed successfully."
        }, status=status.HTTP_200_OK)


class ProfileView(APIView):
    """Get and update user profile - returns appropriate profile based on role"""
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        user = request.user
        
        # Check if user is instructor
        if user.role in ['instructor', 'admin']:
            from instructors.models import InstructorProfile
            from instructors.serializers import InstructorProfileSerializer
            
            # Get or create instructor profile
            instructor_profile, created = InstructorProfile.objects.get_or_create(user=user)
            serializer = InstructorProfileSerializer(instructor_profile)
            return Response(serializer.data)
        else:
            # Return student profile
            profile, created = Profile.objects.get_or_create(user=user)
            serializer = ProfileSerializer(profile)
            return Response(serializer.data)
    
    def put(self, request):
        user = request.user
        
        # Check if user is instructor
        if user.role in ['instructor', 'admin']:
            from instructors.models import InstructorProfile
            from instructors.serializers import InstructorProfileSerializer
            
            instructor_profile, created = InstructorProfile.objects.get_or_create(user=user)
            serializer = InstructorProfileSerializer(instructor_profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        else:
            profile, created = Profile.objects.get_or_create(user=user)
            serializer = ProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
    
    def patch(self, request):
        return self.put(request)


class MeView(APIView):
    """Get and update current user information"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Ensure we have the latest DB state for user and profile
        try:
            user.refresh_from_db()
        except Exception:
            pass
        try:
            # Accessing profile may create it; refresh to get latest wallet
            if hasattr(user, 'profile'):
                user.profile.refresh_from_db()
        except Exception:
            pass

        serializer = MeSerializer(user)
        data = serializer.data
        
        # Add profile data based on role
        if user.role in ['instructor', 'admin']:
            from instructors.models import InstructorProfile
            instructor_profile, _ = InstructorProfile.objects.get_or_create(user=user)
            data['bio'] = instructor_profile.bio
            data['headline'] = instructor_profile.headline
            data['website'] = instructor_profile.website
            data['linkedin'] = instructor_profile.linkedin
            data['twitter'] = instructor_profile.twitter
            data['expertise'] = ', '.join(instructor_profile.expertise_areas) if instructor_profile.expertise_areas else ''
            data['teaching_experience'] = instructor_profile.years_of_experience
        else:
            # Add student profile data if exists
            try:
                profile = user.profile
                data['bio'] = profile.bio
                data['full_name'] = profile.full_name
            except:
                data['bio'] = ''
                data['full_name'] = ''
        
        return Response(data)

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


class UpdateUserRoleView(APIView):
    """Update user role (admin only)"""
    permission_classes = [IsAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        serializer = UpdateUserRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user.role = serializer.validated_data['role']
        user.save()
        
        return Response({
            "message": f"User {user.email} role updated to {user.role}.",
            "user": UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class PromoteToInstructorView(APIView):
    """Promote user to instructor (admin only)"""
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.role = User.Role.INSTRUCTOR
        user.save()
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
        user.save()
        return Response({
            "message": f"User {user.email} has been deactivated."
        }, status=status.HTTP_200_OK)


class ActivateUserView(APIView):
    """Activate user account (admin only)"""
    permission_classes = [IsAdmin]

    def post(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        user.is_active = True
        user.save()
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
        return APIKey.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class APIKeyDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete API key"""
    serializer_class = APIKeySerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    
    def get_queryset(self):
        return APIKey.objects.filter(user=self.request.user)


class APIKeyToggleView(APIView):
    """Toggle API key active status"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, key_id):
        api_key = get_object_or_404(APIKey, id=key_id, user=request.user)
        api_key.is_active = not api_key.is_active
        api_key.save()
        
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

