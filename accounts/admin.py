from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin, UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied

from core.admin import ReadOnlyAdmin
from .models import User, Profile, APIKey


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'created_at', 'updated_at')
    search_fields = ('full_name', 'user__email')
    list_filter = ('created_at',)


@admin.register(APIKey)
class APIKeyAdmin(ReadOnlyAdmin):
    list_display = ('user', 'label', 'prefix', 'created_at', 'last_used_at', 'revoked_at', 'is_active')
    search_fields = ('user__email', 'label', 'prefix')
    list_filter = ('is_active', 'created_at', 'last_used_at', 'revoked_at')
    exclude = ('key_hash',)


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


class AccountUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('email',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AccountUserChangeForm
    add_form = AccountUserCreationForm
    list_display = ('email', 'username', 'role', 'is_active', 'admin_console_only', 'created_at')
    search_fields = ('email', 'username')
    list_filter = ('role', 'is_active', 'admin_console_only')
    ordering = ('email',)
    
    # Required for custom user model with email as USERNAME_FIELD
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username',)}),
        ('Permissions', {'fields': (
            'role', 'is_active', 'is_staff', 'admin_console_only', 'is_superuser', 'groups', 'user_permissions',
        )}),
        ('Important dates', {'fields': ('last_login', 'created_at')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'is_active'),
        }),
    )
    readonly_fields = ('created_at', 'last_login', 'is_staff')

    def has_change_permission(self, request, obj=None):
        if obj is not None and not request.user.is_superuser and (obj.is_staff or obj.is_superuser):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def get_fieldsets(self, request, obj=None):
        if obj is None and not request.user.is_superuser:
            return ((None, {'fields': ('email', 'password1', 'password2', 'is_active')}),)
        return super().get_fieldsets(request, obj)

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if not request.user.is_superuser:
            if obj is None:
                return fields
            return (
                *fields, 'email', 'username', 'password', 'role', 'admin_console_only',
                'is_superuser', 'groups', 'user_permissions',
            )
        if obj is not None and obj.pk == request.user.pk:
            return (*fields, 'role', 'is_active', 'is_superuser')
        return fields

    def user_change_password(self, request, id, form_url=''):
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().user_change_password(request, id, form_url)

    def save_model(self, request, obj, form, change):
        if change and not request.user.is_superuser:
            updated = User.objects.filter(pk=obj.pk, is_staff=False, is_superuser=False).update(is_active=obj.is_active)
            if not updated:
                raise PermissionDenied
            return
        if obj.role == User.Role.ADMIN and (not change or 'role' in form.changed_data):
            obj.admin_console_only = True
        super().save_model(request, obj, form, change)


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(BaseGroupAdmin):
    """Permission grants are administered by superusers."""

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)
