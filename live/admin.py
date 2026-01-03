"""
Live Streaming Django Admin Configuration
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from live.models import (
    LiveSession, SessionParticipant, LiveChatMessage, LiveQuestion,
    LivePoll, PollOption, PollVote, SessionRecording, RecordingView,
    SessionAttendance
)


@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    """Admin for LiveSession model."""
    
    list_display = [
        'title', 'course_link', 'instructor_link', 'session_type',
        'status_badge', 'scheduled_start', 'participant_count_display',
        'duration_display', 'created_at'
    ]
    list_filter = [
        'status', 'session_type', 'platform', 'requires_enrollment',
        'is_public', 'enable_recording', 'scheduled_start'
    ]
    search_fields = [
        'title', 'description', 'course__title',
        'instructor__email', 'instructor__first_name', 'instructor__last_name'
    ]
    date_hierarchy = 'scheduled_start'
    readonly_fields = [
        'stream_key', 'channel_name', 'actual_start', 'actual_end',
        'created_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('course', 'instructor', 'title', 'description', 'session_type')
        }),
        ('Scheduling', {
            'fields': (
                'scheduled_start', 'scheduled_end', 'actual_start', 'actual_end',
                'timezone_info'
            )
        }),
        ('Platform & Access', {
            'fields': (
                'platform', 'meeting_link', 'meeting_id', 'meeting_password',
                'stream_key', 'channel_name', 'app_id'
            )
        }),
        ('Settings', {
            'fields': (
                'max_participants', 'enable_chat', 'enable_qa', 'enable_polls',
                'enable_recording', 'enable_screen_share'
            )
        }),
        ('Access Control', {
            'fields': (
                'requires_enrollment', 'is_public', 'password_protected'
            )
        }),
        ('Status & Features', {
            'fields': ('status', 'is_featured')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def course_link(self, obj):
        """Link to course admin."""
        url = reverse('admin:courses_course_change', args=[obj.course.id])
        return format_html('<a href="{}">{}</a>', url, obj.course.title)
    course_link.short_description = 'Course'
    
    def instructor_link(self, obj):
        """Link to instructor admin."""
        url = reverse('admin:accounts_user_change', args=[obj.instructor.id])
        return format_html('<a href="{}">{}</a>', url, obj.instructor.email)
    instructor_link.short_description = 'Instructor'
    
    def status_badge(self, obj):
        """Display status with color coding."""
        colors = {
            'scheduled': '#ffc107',  # Yellow
            'live': '#28a745',       # Green
            'ended': '#6c757d',      # Gray
            'cancelled': '#dc3545',  # Red
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def participant_count_display(self, obj):
        """Display participant count."""
        count = obj.participant_count()
        if obj.max_participants:
            return f"{count} / {obj.max_participants}"
        return str(count)
    participant_count_display.short_description = 'Participants'
    
    def duration_display(self, obj):
        """Display duration."""
        duration = obj.duration_minutes()
        if duration:
            hours = duration // 60
            minutes = duration % 60
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        return "-"
    duration_display.short_description = 'Duration'


@admin.register(SessionParticipant)
class SessionParticipantAdmin(admin.ModelAdmin):
    """Admin for SessionParticipant model."""
    
    list_display = [
        'user_email', 'session_title', 'status_badge',
        'joined_at', 'duration_display', 'engagement_display',
        'attendance_badge'
    ]
    list_filter = ['status', 'is_moderator', 'joined_at']
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name',
        'session__title'
    ]
    date_hierarchy = 'registered_at'
    readonly_fields = [
        'duration_seconds', 'chat_messages_count', 'questions_asked',
        'polls_answered', 'registered_at', 'updated_at'
    ]
    
    fieldsets = (
        ('Participation', {
            'fields': ('session', 'user', 'status', 'joined_at', 'left_at')
        }),
        ('Engagement Stats', {
            'fields': (
                'duration_seconds', 'chat_messages_count',
                'questions_asked', 'polls_answered'
            )
        }),
        ('Permissions', {
            'fields': ('can_unmute', 'can_share_screen', 'is_moderator')
        }),
        ('Metadata', {
            'fields': ('registered_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_email(self, obj):
        """Get user email."""
        return obj.user.email
    user_email.short_description = 'User'
    
    def session_title(self, obj):
        """Get session title."""
        return obj.session.title
    session_title.short_description = 'Session'
    
    def status_badge(self, obj):
        """Display status with color."""
        colors = {
            'registered': '#17a2b8',  # Blue
            'joined': '#28a745',      # Green
            'left': '#6c757d',        # Gray
            'banned': '#dc3545',      # Red
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def duration_display(self, obj):
        """Display duration."""
        seconds = obj.duration_seconds
        minutes = seconds // 60
        if minutes > 60:
            hours = minutes // 60
            mins = minutes % 60
            return f"{hours}h {mins}m"
        return f"{minutes}m"
    duration_display.short_description = 'Duration'
    
    def engagement_display(self, obj):
        """Display engagement metrics."""
        return format_html(
            '💬 {} | ❓ {} | 📊 {}',
            obj.chat_messages_count, obj.questions_asked, obj.polls_answered
        )
    engagement_display.short_description = 'Engagement'
    
    def attendance_badge(self, obj):
        """Display attendance rate."""
        rate = obj.attendance_rate()
        if rate >= 75:
            color = '#28a745'  # Green
        elif rate >= 50:
            color = '#ffc107'  # Yellow
        else:
            color = '#dc3545'  # Red
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{} %</span>',
            color, rate
        )
    attendance_badge.short_description = 'Attendance'


@admin.register(LiveChatMessage)
class LiveChatMessageAdmin(admin.ModelAdmin):
    """Admin for LiveChatMessage model."""
    
    list_display = [
        'id', 'session_title', 'user_email', 'message_preview',
        'message_type', 'is_pinned', 'is_deleted', 'likes_count',
        'created_at'
    ]
    list_filter = ['message_type', 'is_pinned', 'is_deleted', 'created_at']
    search_fields = [
        'content', 'user__email', 'session__title'
    ]
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'edited_at', 'deleted_at']
    
    def session_title(self, obj):
        """Get session title."""
        return obj.session.title
    session_title.short_description = 'Session'
    
    def user_email(self, obj):
        """Get user email."""
        return obj.user.email if obj.user else 'System'
    user_email.short_description = 'User'
    
    def message_preview(self, obj):
        """Display message preview."""
        if obj.is_deleted:
            return format_html('<i style="color: #dc3545;">[Deleted]</i>')
        preview = obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
        return preview
    message_preview.short_description = 'Message'


@admin.register(LiveQuestion)
class LiveQuestionAdmin(admin.ModelAdmin):
    """Admin for LiveQuestion model."""
    
    list_display = [
        'id', 'session_title', 'user_email', 'question_preview',
        'status_badge', 'upvotes_display', 'is_featured',
        'is_anonymous', 'created_at'
    ]
    list_filter = ['status', 'is_featured', 'is_anonymous', 'created_at']
    search_fields = [
        'question', 'answer', 'user__email', 'session__title'
    ]
    date_hierarchy = 'created_at'
    readonly_fields = ['upvotes', 'answered_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Question', {
            'fields': ('session', 'user', 'question', 'is_anonymous')
        }),
        ('Answer', {
            'fields': ('answer', 'answered_by', 'answered_at', 'status')
        }),
        ('Engagement', {
            'fields': ('upvotes', 'is_featured')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def session_title(self, obj):
        """Get session title."""
        return obj.session.title
    session_title.short_description = 'Session'
    
    def user_email(self, obj):
        """Get user email."""
        if obj.is_anonymous:
            return 'Anonymous'
        return obj.user.email
    user_email.short_description = 'User'
    
    def question_preview(self, obj):
        """Display question preview."""
        preview = obj.question[:60] + '...' if len(obj.question) > 60 else obj.question
        return preview
    question_preview.short_description = 'Question'
    
    def status_badge(self, obj):
        """Display status badge."""
        colors = {
            'pending': '#ffc107',    # Yellow
            'answered': '#28a745',   # Green
            'dismissed': '#6c757d',  # Gray
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def upvotes_display(self, obj):
        """Display upvotes with icon."""
        if obj.upvotes > 10:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">⬆️ {}</span>',
                obj.upvotes
            )
        return f"⬆️ {obj.upvotes}"
    upvotes_display.short_description = 'Upvotes'


class PollOptionInline(admin.TabularInline):
    """Inline for poll options."""
    model = PollOption
    extra = 0
    readonly_fields = ['votes_count']


@admin.register(LivePoll)
class LivePollAdmin(admin.ModelAdmin):
    """Admin for LivePoll model."""
    
    list_display = [
        'id', 'session_title', 'question_preview', 'status_badge',
        'total_votes_display', 'started_at', 'ends_at', 'created_at'
    ]
    list_filter = ['status', 'allow_multiple_answers', 'is_anonymous', 'created_at']
    search_fields = ['question', 'description', 'session__title']
    date_hierarchy = 'created_at'
    readonly_fields = ['started_at', 'created_at', 'updated_at']
    inlines = [PollOptionInline]
    
    fieldsets = (
        ('Poll', {
            'fields': ('session', 'created_by', 'question', 'description')
        }),
        ('Settings', {
            'fields': (
                'status', 'allow_multiple_answers',
                'show_results_immediately', 'is_anonymous'
            )
        }),
        ('Duration', {
            'fields': ('duration_seconds', 'started_at', 'ends_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def session_title(self, obj):
        """Get session title."""
        return obj.session.title
    session_title.short_description = 'Session'
    
    def question_preview(self, obj):
        """Display question preview."""
        preview = obj.question[:60] + '...' if len(obj.question) > 60 else obj.question
        return preview
    question_preview.short_description = 'Question'
    
    def status_badge(self, obj):
        """Display status badge."""
        colors = {
            'draft': '#6c757d',    # Gray
            'active': '#28a745',   # Green
            'closed': '#dc3545',   # Red
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def total_votes_display(self, obj):
        """Display total votes."""
        votes = obj.total_votes()
        return format_html('<strong>{}</strong> votes', votes)
    total_votes_display.short_description = 'Total Votes'


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    """Admin for PollOption model."""
    
    list_display = [
        'id', 'poll_question', 'text', 'order',
        'votes_count_display', 'percentage_display'
    ]
    list_filter = ['poll__status']
    search_fields = ['text', 'poll__question']
    readonly_fields = ['votes_count']
    
    def poll_question(self, obj):
        """Get poll question."""
        return obj.poll.question
    poll_question.short_description = 'Poll'
    
    def votes_count_display(self, obj):
        """Display votes with styling."""
        return format_html('<strong>{}</strong>', obj.votes_count)
    votes_count_display.short_description = 'Votes'
    
    def percentage_display(self, obj):
        """Display percentage with bar."""
        percentage = obj.vote_percentage()
        color = '#28a745' if percentage > 50 else '#17a2b8'
        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; color: white; '
            'padding: 2px; text-align: center; border-radius: 3px; font-size: 11px;">'
            '{:.1f}%</div></div>',
            percentage, color, percentage
        )
    percentage_display.short_description = 'Percentage'


@admin.register(SessionRecording)
class SessionRecordingAdmin(admin.ModelAdmin):
    """Admin for SessionRecording model."""
    
    list_display = [
        'title', 'session_title', 'processing_status_badge',
        'duration_display', 'file_size_mb', 'views_count',
        'is_public', 'recorded_at'
    ]
    list_filter = [
        'processing_status', 'is_public', 'requires_enrollment',
        'recorded_at'
    ]
    search_fields = ['title', 'description', 'session__title']
    date_hierarchy = 'recorded_at'
    readonly_fields = [
        'views_count', 'downloads_count', 'recorded_at',
        'processed_at', 'published_at'
    ]
    
    fieldsets = (
        ('Recording', {
            'fields': ('session', 'title', 'description')
        }),
        ('File Information', {
            'fields': (
                'video_url', 'thumbnail_url', 'duration_seconds',
                'file_size_mb'
            )
        }),
        ('Processing', {
            'fields': ('processing_status', 'error_message')
        }),
        ('Access Control', {
            'fields': ('is_public', 'requires_enrollment')
        }),
        ('Analytics', {
            'fields': ('views_count', 'downloads_count')
        }),
        ('Metadata', {
            'fields': ('recorded_at', 'processed_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )
    
    def session_title(self, obj):
        """Get session title."""
        return obj.session.title
    session_title.short_description = 'Session'
    
    def processing_status_badge(self, obj):
        """Display processing status."""
        colors = {
            'pending': '#ffc107',    # Yellow
            'processing': '#17a2b8', # Blue
            'ready': '#28a745',      # Green
            'failed': '#dc3545',     # Red
        }
        color = colors.get(obj.processing_status, '#6c757d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 3px;">{}</span>',
            color, obj.get_processing_status_display()
        )
    processing_status_badge.short_description = 'Status'
    
    def duration_display(self, obj):
        """Display formatted duration."""
        return obj.duration_formatted()
    duration_display.short_description = 'Duration'


@admin.register(RecordingView)
class RecordingViewAdmin(admin.ModelAdmin):
    """Admin for RecordingView model."""
    
    list_display = [
        'user_email', 'recording_title', 'watch_percentage_bar',
        'completed', 'device_type', 'last_viewed_at'
    ]
    list_filter = ['completed', 'device_type', 'browser', 'last_viewed_at']
    search_fields = ['user__email', 'recording__title']
    date_hierarchy = 'first_viewed_at'
    readonly_fields = ['first_viewed_at', 'last_viewed_at']
    
    def user_email(self, obj):
        """Get user email."""
        return obj.user.email
    user_email.short_description = 'User'
    
    def recording_title(self, obj):
        """Get recording title."""
        return obj.recording.title
    recording_title.short_description = 'Recording'
    
    def watch_percentage_bar(self, obj):
        """Display watch percentage with bar."""
        percentage = obj.watch_percentage()
        if percentage >= 90:
            color = '#28a745'  # Green
        elif percentage >= 50:
            color = '#ffc107'  # Yellow
        else:
            color = '#dc3545'  # Red
        
        return format_html(
            '<div style="width: 150px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; color: white; '
            'padding: 3px; text-align: center; border-radius: 3px; font-weight: bold;">'
            '{}%</div></div>',
            percentage, color, percentage
        )
    watch_percentage_bar.short_description = 'Watch Progress'


@admin.register(SessionAttendance)
class SessionAttendanceAdmin(admin.ModelAdmin):
    """Admin for SessionAttendance model."""
    
    list_display = [
        'session_title', 'user_email', 'attendance_badge',
        'attendance_percentage_bar', 'verified', 'created_at'
    ]
    list_filter = ['marked_present', 'verified_at', 'created_at']
    search_fields = [
        'participant__user__email', 'session__title', 'notes'
    ]
    date_hierarchy = 'created_at'
    readonly_fields = ['verified_at', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Attendance', {
            'fields': (
                'session', 'participant', 'marked_present',
                'attendance_percentage'
            )
        }),
        ('Verification', {
            'fields': ('verified_by', 'verified_at', 'notes')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def session_title(self, obj):
        """Get session title."""
        return obj.session.title
    session_title.short_description = 'Session'
    
    def user_email(self, obj):
        """Get user email."""
        return obj.participant.user.email
    user_email.short_description = 'User'
    
    def attendance_badge(self, obj):
        """Display attendance status."""
        if obj.marked_present:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 3px 10px; border-radius: 3px; font-weight: bold;">✓ Present</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; '
            'padding: 3px 10px; border-radius: 3px; font-weight: bold;">✗ Absent</span>'
        )
    attendance_badge.short_description = 'Status'
    
    def attendance_percentage_bar(self, obj):
        """Display attendance percentage with bar."""
        percentage = obj.attendance_percentage
        if percentage >= 75:
            color = '#28a745'  # Green
        elif percentage >= 50:
            color = '#ffc107'  # Yellow
        else:
            color = '#dc3545'  # Red
        
        return format_html(
            '<div style="width: 120px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width: {}%; background-color: {}; color: white; '
            'padding: 3px; text-align: center; border-radius: 3px; font-weight: bold;">'
            '{}%</div></div>',
            percentage, color, percentage
        )
    attendance_percentage_bar.short_description = 'Attendance %'
    
    def verified(self, obj):
        """Display verification status."""
        if obj.verified_at:
            return format_html(
                '<span style="color: #28a745; font-weight: bold;">✓ Verified</span>'
            )
        return format_html(
            '<span style="color: #6c757d;">Not verified</span>'
        )
    verified.short_description = 'Verification'
