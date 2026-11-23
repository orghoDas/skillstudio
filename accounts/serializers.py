from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import get_user_model

from accounts.models import Profile, APIKey
from accounts.utils import signup_role_for_email

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    """Self-registration. The role is NOT chosen by the client: it is derived
    from the email domain (accounts.utils.signup_role_for_email, Decision D-02).
    Any ``role`` sent by the client is ignored."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)
    role = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("email", 'username', "password", "password2", "role")
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def validate_email(self, value):
        value = User.objects.normalize_email(value)
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        try:
            signup_role_for_email(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        return User.objects.create_user(
            email=validated_data["email"],
            username=validated_data.get("username"),
            password=validated_data["password"],
            role=signup_role_for_email(validated_data["email"]),
        )


class AccountProfileSerializer(serializers.ModelSerializer):
    """Serializer for shared account-owned profile data."""

    # Balance is derived from the canonical students.Wallet ledger, not stored
    # on Profile. Kept in the response under the same `wallet` key for clients.
    wallet = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = (
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "location",
            "bio",
            "avatar",
            "social_links",
            "interests",
            "wallet",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def get_wallet(self, obj) -> dict:
        from students.services import get_or_create_wallet
        return get_or_create_wallet(obj.user).balance


class ProfileSerializer(AccountProfileSerializer):
    role = serializers.CharField(source='user.role', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Profile
        fields = ("role", "email", "first_name", "last_name", "full_name", "phone", "location", "bio", "avatar", "social_links", "interests", "wallet", "created_at", "updated_at")
        read_only_fields = ("role", "email", "created_at", "updated_at")


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
    account_profile = serializers.SerializerMethodField()
    student_profile = serializers.SerializerMethodField()
    instructor_profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "role",
            "is_active",
            "created_at",
            "account_profile",
            "student_profile",
            "instructor_profile",
        )
        read_only_fields = ('id', 'email', 'role', 'is_active', 'created_at')

    def get_account_profile(self, obj) -> dict:
        profile, _ = Profile.objects.get_or_create(user=obj)
        return AccountProfileSerializer(profile).data

    def get_student_profile(self, obj) -> dict | None:
        if obj.role != User.Role.STUDENT:
            return None

        from students.serializers import StudentProfileSerializer
        from students.services import get_or_create_student_profile

        return StudentProfileSerializer(get_or_create_student_profile(obj)).data

    def get_instructor_profile(self, obj) -> dict | None:
        if obj.role not in (User.Role.INSTRUCTOR, User.Role.ADMIN):
            return None

        from instructors.serializers import InstructorProfileSerializer
        from instructors.services import get_or_create_instructor_profile

        return InstructorProfileSerializer(get_or_create_instructor_profile(obj)).data

    def update(self, instance, validated_data):
        # Update user fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if validated_data:
            instance.save(update_fields=validated_data.keys())

        return instance


class UnifiedProfileSerializer(MeSerializer):
    """Stable profile envelope for account-owned and role-owned profile data."""

    pass


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password2": "Passwords do not match."})
        return attrs


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = (
            "id",
            "label",
            "prefix",
            "scopes",
            "created_at",
            "last_used_at",
            "revoked_at",
            "is_active",
        )
        read_only_fields = (
            "id",
            "prefix",
            "scopes",
            "created_at",
            "last_used_at",
            "revoked_at",
            "is_active",
        )


class CreateAPIKeySerializer(serializers.Serializer):
    label = serializers.CharField(max_length=255)
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=APIKey.Scope.choices),
        required=False,
        allow_empty=True,
    )


class UpdateUserRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=User.Role.choices, required=True)
