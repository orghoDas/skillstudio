from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import InstructorProfile, InstructorPayout


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'headline_display',
        'is_verified',
        'total_courses',
        'total_students',
        'revenue_display',
        'rating_display',
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
        'average_rating',
        'total_reviews',
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
                'average_rating',
                'total_reviews',
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
        return format_html('${:,.2f}', obj.total_revenue)
    revenue_display.short_description = 'Revenue'
    
    def rating_display(self, obj):
        color = 'green' if obj.average_rating >= 4.0 else 'orange' if obj.average_rating >= 3.0 else 'red'
        return format_html(
            '<span style="color: {};">{:.2f} ({} reviews)</span>',
            color,
            obj.average_rating,
            obj.total_reviews
        )
    rating_display.short_description = 'Rating'
    
    def verify_instructors(self, request, queryset):
        for profile in queryset:
            profile.verify()
        self.message_user(request, f"{queryset.count()} instructors verified.")
    verify_instructors.short_description = "Verify selected instructors"


@admin.register(InstructorPayout)
class InstructorPayoutAdmin(admin.ModelAdmin):
    list_display = [
        'instructor_link',
        'amount_display',
        'status_display',
        'payment_method',
        'created_at',
        'processed_at',
    ]
    list_filter = [
        'status',
        'payment_method',
        'created_at',
        'processed_at',
    ]
    search_fields = [
        'instructor__email',
        'transaction_id',
    ]
    readonly_fields = [
        'id',
        'instructor',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('Payout Information', {
            'fields': ('id', 'instructor', 'amount', 'currency')
        }),
        ('Status', {
            'fields': ('status', 'processed_at')
        }),
        ('Payment Details', {
            'fields': (
                'payment_method',
                'payment_details',
                'transaction_id',
            )
        }),
        ('Metadata', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def instructor_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.instructor.id])
        return format_html('<a href="{}">{}</a>', url, obj.instructor.email)
    instructor_link.short_description = 'Instructor'
    
    def amount_display(self, obj):
        return format_html('${:,.2f} {}', obj.amount, obj.currency)
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'cancelled': 'gray',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_display.short_description = 'Status'
