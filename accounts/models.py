from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import uuid

# Create your models here.
class UserManager(BaseUserManager):
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
        return self.create_user(email, password, **extra_fields)


# PostgreSQL Equivalent:
# CREATE TABLE accounts_user (
#     id SERIAL PRIMARY KEY,
#     password VARCHAR(128) NOT NULL,
#     last_login TIMESTAMP WITH TIME ZONE,
#     is_superuser BOOLEAN NOT NULL DEFAULT FALSE,
#     username VARCHAR(150) UNIQUE,
#     email VARCHAR(254) UNIQUE NOT NULL,
#     role VARCHAR(20) NOT NULL DEFAULT 'student' CHECK (role IN ('admin', 'student', 'instructor')),
#     is_active BOOLEAN NOT NULL DEFAULT TRUE,
#     is_staff BOOLEAN NOT NULL DEFAULT FALSE,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX accounts_user_email_idx ON accounts_user(email);
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
    created_at = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return f'{self.email} ({self.role})'


# PostgreSQL Equivalent:
# CREATE TABLE accounts_profile (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER UNIQUE NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     full_name VARCHAR(255),
#     bio TEXT,
#     avatar VARCHAR(200),
#     social_links JSONB DEFAULT '{}',
#     interests JSONB DEFAULT '[]',
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX accounts_profile_user_id_idx ON accounts_profile(user_id);
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    avatar = models.URLField(blank=True, null=True)
    social_links = models.JSONField(default=dict, blank=True)
    interests = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.email
    

# PostgreSQL Equivalent:
# CREATE TABLE accounts_emailverificationtoken (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     token UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
#     is_used BOOLEAN NOT NULL DEFAULT FALSE
# );
# CREATE INDEX accounts_emailverificationtoken_user_id_idx ON accounts_emailverificationtoken(user_id);
# CREATE INDEX accounts_emailverificationtoken_token_idx ON accounts_emailverificationtoken(token);
class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return f'EmailVerification for {self.user.email} - Used: {self.is_used}'
    

# PostgreSQL Equivalent:
# CREATE TABLE accounts_passwordresettoken (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     token UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
#     expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX accounts_passwordresettoken_user_id_idx ON accounts_passwordresettoken(user_id);
# CREATE INDEX accounts_passwordresettoken_token_idx ON accounts_passwordresettoken(token);
class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique = True, editable=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'PasswordResetToken for {self.user.email}'
    

# PostgreSQL Equivalent:
# CREATE TABLE accounts_apikey (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     key UUID UNIQUE NOT NULL DEFAULT gen_random_uuid(),
#     label VARCHAR(255) NOT NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     is_active BOOLEAN NOT NULL DEFAULT TRUE
# );
# CREATE INDEX accounts_apikey_user_id_idx ON accounts_apikey(user_id);
# CREATE INDEX accounts_apikey_key_idx ON accounts_apikey(key);
class APIKey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    label = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'APIKey {self.label} for {self.user.email}'
