from django.db.models.functions import Lower
from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import hashlib
import secrets

from .utils import profile_display_name


class UserManager(BaseUserManager):
    @classmethod
    def normalize_email(cls, email):
        return super().normalize_email(email).strip().lower()

    def get_by_natural_key(self, username):
        return self.get(email__iexact=self.normalize_email(username))

    async def aget_by_natural_key(self, username):
        return await self.aget(email__iexact=self.normalize_email(username))

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get('is_superuser') is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get('role') != User.Role.ADMIN:
            raise ValueError("Superuser must have role=admin.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        STUDENT = 'student', 'Student'
        INSTRUCTOR = 'instructor', 'Instructor'
    username = models.CharField(max_length=150, unique=True, null=True, blank=True)    
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    admin_console_only = models.BooleanField(
        default=False,
        db_default=False,
        help_text='Restricts this account to the admin console. Website sign-in and API credentials are disabled.',
    )
    created_at = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower('email'), name='unique_user_email_case_insensitive'),
            models.CheckConstraint(
                condition=(
                    models.Q(role='admin', is_staff=True)
                    | ~models.Q(role='admin')
                ),
                name='admin_role_requires_staff',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(is_superuser=False)
                    | models.Q(role='admin', is_staff=True)
                ),
                name='superuser_requires_admin_role_staff',
            ),
            models.CheckConstraint(
                condition=models.Q(role='admin') | models.Q(is_staff=False),
                name='non_admin_role_cannot_be_staff',
            ),
        ]

    def __str__(self):
        return f'{self.email} ({self.role})'

    def get_full_name(self):
        return profile_display_name(self)

    @property
    def is_platform_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    def normalize_role_flags(self):
        if self.is_superuser and self.role != self.Role.ADMIN:
            if not self._state.adding:
                raise ValidationError({'role': 'A superuser must retain the admin role.'})
            self.role = self.Role.ADMIN
        self.is_staff = self.role == self.Role.ADMIN

    def clean(self):
        super().clean()
        self.email = User.objects.normalize_email(self.email)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is None or 'email' in update_fields:
            self.email = User.objects.normalize_email(self.email)
        if update_fields is not None:
            update_fields = set(update_fields)
            kwargs['update_fields'] = update_fields
            if not update_fields.intersection({'role', 'is_staff', 'is_superuser'}):
                return super().save(*args, **kwargs)

        original_role = self.role
        original_is_staff = self.is_staff
        self.normalize_role_flags()
        if update_fields is not None:
            if self.role != original_role or ('is_superuser' in update_fields and self.is_superuser):
                update_fields.add('role')
            if self.is_staff != original_is_staff or 'role' in update_fields:
                update_fields.add('is_staff')
        super().save(*args, **kwargs)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    avatar = models.URLField(blank=True, null=True)
    social_links = models.JSONField(default=dict, blank=True)
    interests = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    # Wallet balance moved to the canonical students.Wallet ledger.

    def __str__(self):
        return self.full_name or f"{self.first_name} {self.last_name}".strip() or self.user.email
    

class APIKey(models.Model):
    class Scope(models.TextChoices):
        READ = 'read', 'Read'
        WRITE = 'write', 'Write'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key_hash = models.CharField(max_length=64, unique=True)
    prefix = models.CharField(max_length=16, db_index=True)
    label = models.CharField(max_length=255)
    scopes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    @staticmethod
    def generate_secret():
        return f"ss_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_secret(secret):
        return hashlib.sha256(secret.encode("utf-8")).hexdigest()

    @classmethod
    def create_for_user(cls, user, label, scopes=None):
        secret = cls.generate_secret()
        api_key = cls.objects.create(
            user=user,
            label=label,
            scopes=scopes or [],
            prefix=secret[:16],
            key_hash=cls.hash_secret(secret),
        )
        return api_key, secret

    def revoke(self):
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])

    def __str__(self):
        return f'APIKey {self.label} for {self.user.email}'
