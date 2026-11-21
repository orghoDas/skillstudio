from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from .models import User, Profile, APIKey


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'created_at', 'updated_at')
    search_fields = ('full_name', 'user__email')
    list_filter = ('created_at',)


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'label', 'prefix', 'created_at', 'last_used_at', 'revoked_at', 'is_active')
    search_fields = ('user__email', 'label', 'prefix')
    list_filter = ('is_active', 'created_at', 'last_used_at', 'revoked_at')
    readonly_fields = ('prefix', 'key_hash', 'created_at', 'last_used_at', 'revoked_at')


class AccountUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        field_classes = {}

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        if role and role != User.Role.ADMIN and (self.instance.is_superuser or cleaned.get('is_superuser')):
            self.add_error('role', 'A superuser must retain the admin role.')
        return cleaned


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AccountUserChangeForm
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
            'fields': ('email', 'password1', 'password2', 'role', 'is_active'),
        }),
    )
    readonly_fields = ('created_at', 'last_login', 'is_staff')
