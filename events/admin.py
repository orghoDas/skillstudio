from django.contrib import admin
from .models import Event, EventRegistration, EventFeedback, EventAttendanceLog, EventResource


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Admin interface for Events."""
    list_display = [
        'id', 'title', 'event_type', 'host_email', 'scheduled_for',
        'status', 'attendee_count', 'max_seats', 'price', 'is_featured', 'created_at'
    ]
    list_filter = ['event_type', 'status', 'is_featured', 'is_free', 'scheduled_for', 'created_at']
    search_fields = ['title', 'description', 'host__email']
    readonly_fields = ['created_at', 'updated_at', 'attendee_count', 'seats_available']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('host', 'course', 'title', 'description', 'event_type', 'cover_image')
        }),
        ('Scheduling', {
            'fields': ('scheduled_for', 'duration_minutes', 'timezone')
        }),
        ('Capacity & Pricing', {
            'fields': ('max_seats', 'price', 'is_free')
        }),
        ('Access & Requirements', {
            'fields': ('requires_enrollment', 'prerequisites')
        }),
        ('Meeting Details', {
            'fields': ('meeting_link', 'meeting_password', 'platform')
        }),
        ('Status & Publishing', {
            'fields': ('status', 'is_featured')
        }),
        ('Tracking', {
            'fields': ('created_at', 'updated_at', 'attendee_count', 'seats_available')
        }),
    )
    
    def host_email(self, obj):
        return obj.host.email
    host_email.short_description = 'Host'
    
    def attendee_count(self, obj):
        return obj.attendee_count()
    attendee_count.short_description = 'Attendees'


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    """Admin interface for Event Registrations."""
    list_display = [
        'id', 'event_title', 'user_email', 'status', 'payment_status',
        'payment_amount', 'attended', 'registered_on'
    ]
    list_filter = ['status', 'payment_status', 'attended', 'registered_on']
    search_fields = ['event__title', 'user__email']
    readonly_fields = ['registered_on', 'attended_at', 'cancelled_at']
    
    fieldsets = (
        ('Registration Info', {
            'fields': ('event', 'user', 'status')
        }),
        ('Payment', {
            'fields': ('payment_status', 'payment_amount')
        }),
        ('Attendance', {
            'fields': ('attended', 'attended_at')
        }),
        ('Timestamps', {
            'fields': ('registered_on', 'cancelled_at')
        }),
    )
    
    def event_title(self, obj):
        return obj.event.title
    event_title.short_description = 'Event'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'


@admin.register(EventFeedback)
class EventFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for Event Feedback."""
    list_display = [
        'id', 'event_title', 'user_email', 'rating',
        'content_quality', 'host_performance', 'would_recommend', 'created_at'
    ]
    list_filter = ['rating', 'would_recommend', 'created_at']
    search_fields = ['event__title', 'user__email', 'title', 'comment']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Feedback Info', {
            'fields': ('event', 'user')
        }),
        ('Ratings', {
            'fields': ('rating', 'content_quality', 'host_performance', 'would_recommend')
        }),
        ('Comments', {
            'fields': ('title', 'comment')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    
    def event_title(self, obj):
        return obj.event.title
    event_title.short_description = 'Event'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'


@admin.register(EventAttendanceLog)
class EventAttendanceLogAdmin(admin.ModelAdmin):
    """Admin interface for Attendance Logs."""
    list_display = [
        'id', 'registration_event', 'registration_user',
        'joined_at', 'left_at', 'duration_minutes'
    ]
    list_filter = ['joined_at']
    search_fields = ['registration__event__title', 'registration__user__email']
    readonly_fields = ['joined_at']
    
    def registration_event(self, obj):
        return obj.registration.event.title
    registration_event.short_description = 'Event'
    
    def registration_user(self, obj):
        return obj.registration.user.email
    registration_user.short_description = 'User'


@admin.register(EventResource)
class EventResourceAdmin(admin.ModelAdmin):
    """Admin interface for Event Resources."""
    list_display = [
        'id', 'event_title', 'title', 'resource_type',
        'attendees_only', 'available_after_event', 'uploaded_at'
    ]
    list_filter = ['resource_type', 'attendees_only', 'available_after_event', 'uploaded_at']
    search_fields = ['event__title', 'title', 'description']
    readonly_fields = ['uploaded_at']
    
    fieldsets = (
        ('Resource Info', {
            'fields': ('event', 'title', 'description', 'resource_type')
        }),
        ('Content', {
            'fields': ('file', 'url')
        }),
        ('Access Control', {
            'fields': ('available_after_event', 'attendees_only')
        }),
        ('Metadata', {
            'fields': ('uploaded_at',)
        }),
    )
    
    def event_title(self, obj):
        return obj.event.title
    event_title.short_description = 'Event'
