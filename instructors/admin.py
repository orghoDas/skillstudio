from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import InstructorProfile


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'headline_display',
        'is_verified',
        'total_courses',
        'total_students',
        'revenue_display',
        'created_at',
    ]
    list_filter = [
        'is_verified',
        'created_at',
        'verified_at',
    ]
    search_fields = [
        'user__email',
        'user__username',
        'bio',
        'headline',
    ]
    readonly_fields = [
        'id',
        'total_courses',
        'total_students',
        'total_revenue',
        'verified_at',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('User', {
            'fields': ('id', 'user')
        }),
        ('Professional Information', {
            'fields': (
                'bio',
                'headline',
                'website',
                'linkedin',
                'twitter',
            )
        }),
        ('Expertise', {
            'fields': (
                'expertise_areas',
                'years_of_experience',
                'certifications',
                'education',
            )
        }),
        ('Statistics', {
            'fields': (
                'total_courses',
                'total_students',
                'total_revenue',
            )
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    actions = ['verify_instructors']
    
    def user_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    
    def headline_display(self, obj):
        return obj.headline[:50] + '...' if len(obj.headline) > 50 else obj.headline
    headline_display.short_description = 'Headline'
    
    def revenue_display(self, obj):
        return format_html('${}', f'{obj.total_revenue:,.2f}')
    revenue_display.short_description = 'Revenue'
    
    def verify_instructors(self, request, queryset):
        for profile in queryset:
            profile.verify()
        self.message_user(request, f"{queryset.count()} instructors verified.")
    verify_instructors.short_description = "Verify selected instructors"
