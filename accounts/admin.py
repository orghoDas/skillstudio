from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile, EmailVerificationToken, PasswordResetToken, APIKey


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'created_at', 'updated_at')
    search_fields = ('full_name', 'user__email')
    list_filter = ('created_at',)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'expires_at', 'is_used')
    search_fields = ('user__email', 'token')
    list_filter = ('is_used', 'created_at', 'expires_at')
    readonly_fields = ('token', 'created_at')


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'token', 'created_at', 'expires_at')
    search_fields = ('user__email', 'token')
    list_filter = ('created_at', 'expires_at')
    readonly_fields = ('token', 'created_at')


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'key', 'created_at', 'is_active')
    search_fields = ('user__email', 'label', 'key')
    list_filter = ('is_active', 'created_at')
    readonly_fields = ('key', 'created_at')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'role', 'is_active', 'is_staff', 'created_at')
    search_fields = ('email', 'username')
    list_filter = ('role', 'is_active', 'is_staff')
    ordering = ('email',)
    
    # Required for custom user model with email as USERNAME_FIELD
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username',)}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_active', 'is_staff'),
        }),
    )
    readonly_fields = ('created_at', 'last_login')