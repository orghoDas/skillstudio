from django.contrib import admin
from .models import AdminAction, ContentModerationQueue, PlatformSettings, SystemAlert


@admin.register(AdminAction)
class AdminActionAdmin(admin.ModelAdmin):
    list_display = ['id', 'admin_user', 'action_type', 'target_model', 'target_id', 'created_at']
    list_filter = ['action_type', 'target_model', 'created_at']
    search_fields = ['admin_user__email', 'description', 'target_model']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False  # Actions are created programmatically
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser  # Only superusers can delete logs


@admin.register(ContentModerationQueue)
class ContentModerationQueueAdmin(admin.ModelAdmin):
    list_display = ['id', 'content_type', 'content_id', 'status', 'reported_by', 'reviewed_by', 'created_at']
    list_filter = ['status', 'content_type', 'created_at']
    search_fields = ['reason', 'admin_notes']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Content Information', {
            'fields': ('content_type', 'content_id', 'reported_by', 'reason')
        }),
        ('Review Information', {
            'fields': ('status', 'reviewed_by', 'reviewed_at', 'admin_notes')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value_preview', 'data_type', 'is_public', 'updated_at']
    list_filter = ['data_type', 'is_public']
    search_fields = ['key', 'description']
    readonly_fields = ['updated_at', 'created_at']
    
    fieldsets = (
        ('Setting Information', {
            'fields': ('key', 'value', 'description', 'data_type', 'is_public')
        }),
        ('Metadata', {
            'fields': ('updated_by', 'updated_at', 'created_at')
        }),
    )
    
    def value_preview(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value
    value_preview.short_description = 'Value'


@admin.register(SystemAlert)
class SystemAlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'alert_type', 'is_active', 'start_time', 'end_time', 'created_by']
    list_filter = ['alert_type', 'is_active', 'created_at']
    search_fields = ['title', 'message']
    readonly_fields = ['created_at']
    date_hierarchy = 'start_time'
    
    fieldsets = (
        ('Alert Information', {
            'fields': ('title', 'message', 'alert_type', 'is_active')
        }),
        ('Targeting', {
            'fields': ('target_roles', 'start_time', 'end_time')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at')
        }),
    )

