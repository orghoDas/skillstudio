from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from accounts.models import Profile, EmailVerificationToken, PasswordResetToken, APIKey

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(
        choices=[User.Role.STUDENT, User.Role.INSTRUCTOR],
        required=False,
        default=User.Role.STUDENT,
        help_text="User role: 'student' or 'instructor'. Defaults to 'student'."
    )

    class Meta:
        model = User
        fields = ("email", 'username', "password", "password2", "role")
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate(self, attrs):
        # Validate passwords match
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        
        # Validate role - only allow student or instructor during registration
        role = attrs.get('role', User.Role.STUDENT)
        if role not in [User.Role.STUDENT, User.Role.INSTRUCTOR]:
            raise serializers.ValidationError({
                "role": "Only 'student' or 'instructor' roles are allowed during registration."
            })
        
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        # Use provided role or default to STUDENT
        role = validated_data.pop('role', User.Role.STUDENT)
        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data.get("username"),
            password=validated_data["password"],
            role=role
        )
        
        # Create email verification token
        EmailVerificationToken.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        return user


class ProfileSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source='user.role', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = Profile
        fields = ("role", "email", "first_name", "last_name", "full_name", "phone", "location", "bio", "avatar", "social_links", "interests", "wallet", "created_at", "updated_at")
        read_only_fields = ("role", "email", "wallet", "created_at", "updated_at")


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user serializer with minimal fields for nested serialization."""
    class Meta:
        model = User
        fields = ("id", "email", "username", "role")
        read_only_fields = ("id", "email", "username", "role")


class UserSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ("id", "email", "username", "role", "is_active", "created_at", "profile")
        read_only_fields = ("id", "email", "created_at")


class MeSerializer(serializers.ModelSerializer):
    profile = ProfileSerializer()

    class Meta:
        model = User
        fields = ("id", "email", "username", 'role', 'is_active', 'created_at', 'profile')
        read_only_fields = ('id', 'email', 'role', 'created_at')

    def update(self, instance, validated_data):
        profile_data = validated_data.pop('profile', None)
        
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Update profile if provided
        if profile_data:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password2": "Passwords do not match."})
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.UUIDField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Passwords do not match."})
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.UUIDField(required=True)


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ("id", "key", "label", "created_at", "is_active")
        read_only_fields = ("id", "key", "created_at")


class CreateAPIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ("label",)


class UpdateUserRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices, required=True)
