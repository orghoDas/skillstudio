from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile, EmailVerificationToken, PasswordResetToken

admin.site.register(Profile)
admin.site.register(EmailVerificationToken)
admin.site.register(PasswordResetToken)

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