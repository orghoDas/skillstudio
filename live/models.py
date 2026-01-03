"""
Live Streaming Models
Handles live classes, streaming sessions, chat, polls, and recordings for courses.
"""

from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.db.models import Avg, Count, Q
from decimal import Decimal

User = settings.AUTH_USER_MODEL


class LiveSession(models.Model):
    """
    Live streaming session for a course.
    Can be a live class, workshop, webinar, or Q&A session.
    """
    SESSION_TYPES = [
        ('class', 'Live Class'),
        ('workshop', 'Workshop'),
        ('webinar', 'Webinar'),
        ('qa', 'Q&A Session'),
        ('office_hours', 'Office Hours'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('live', 'Live Now'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    ]
    
    PLATFORM_CHOICES = [
        ('agora', 'Agora'),
        ('zoom', 'Zoom'),
        ('meet', 'Google Meet'),
        ('teams', 'Microsoft Teams'),
        ('custom', 'Custom Platform'),
    ]
    
    # Basic Information
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='live_sessions'
    )
    instructor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='hosted_sessions'
    )
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='class')
    
    # Scheduling
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    timezone_info = models.CharField(max_length=50, default='UTC')
    
    # Platform & Access
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='agora')
    meeting_link = models.URLField(blank=True)
    meeting_id = models.CharField(max_length=255, blank=True)
    meeting_password = models.CharField(max_length=100, blank=True)
    
    # Agora/Custom streaming details
    stream_key = models.CharField(max_length=255, blank=True)
    channel_name = models.CharField(max_length=255, blank=True)
    app_id = models.CharField(max_length=255, blank=True)
    
    # Settings
    max_participants = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)]
    )
    enable_chat = models.BooleanField(default=True)
    enable_qa = models.BooleanField(default=True)
    enable_polls = models.BooleanField(default=True)
    enable_recording = models.BooleanField(default=True)
    enable_screen_share = models.BooleanField(default=True)
    
    # Access Control
    requires_enrollment = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False)
    password_protected = models.BooleanField(default=False)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    is_featured = models.BooleanField(default=False)
    
    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-scheduled_start']
        indexes = [
            models.Index(fields=['course', 'status']),
            models.Index(fields=['instructor']),
            models.Index(fields=['scheduled_start']),
            models.Index(fields=['status', 'scheduled_start']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.scheduled_start.strftime('%Y-%m-%d %H:%M')}"
    
    def is_upcoming(self):
        """Check if session is upcoming."""
        return self.status == 'scheduled' and timezone.now() < self.scheduled_start
    
    def is_live(self):
        """Check if session is currently live."""
        return self.status == 'live'
    
    def is_past(self):
        """Check if session has ended."""
        return self.status == 'ended' or (
            self.scheduled_end and timezone.now() > self.scheduled_end
        )
    
    def duration_minutes(self):
        """Get scheduled duration in minutes."""
        if self.scheduled_end and self.scheduled_start:
            delta = self.scheduled_end - self.scheduled_start
            return int(delta.total_seconds() / 60)
        return 0
    
    def actual_duration_minutes(self):
        """Get actual duration in minutes."""
        if self.actual_end and self.actual_start:
            delta = self.actual_end - self.actual_start
            return int(delta.total_seconds() / 60)
        return 0
    
    def participant_count(self):
        """Get total number of participants."""
        return self.participants.filter(status='joined').count()
    
    def available_slots(self):
        """Get number of available participant slots."""
        if not self.max_participants:
            return None
        return max(0, self.max_participants - self.participant_count())


class SessionParticipant(models.Model):
    """
    Tracks user participation in live sessions.
    """
    STATUS_CHOICES = [
        ('registered', 'Registered'),
        ('joined', 'Joined'),
        ('left', 'Left'),
        ('banned', 'Banned'),
    ]
    
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='live_participations'
    )
    
    # Participation tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='registered')
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    
    # Engagement
    chat_messages_count = models.IntegerField(default=0)
    questions_asked = models.IntegerField(default=0)
    polls_answered = models.IntegerField(default=0)
    
    # Permissions
    can_unmute = models.BooleanField(default=False)
    can_share_screen = models.BooleanField(default=False)
    is_moderator = models.BooleanField(default=False)
    
    # Tracking
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['session', 'user']
        indexes = [
            models.Index(fields=['session', 'status']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.session.title}"
    
    def attendance_rate(self):
        """Calculate attendance percentage."""
        session_duration = self.session.actual_duration_minutes()
        if not session_duration:
            return 0
        return min(100, int((self.duration_seconds / 60) / session_duration * 100))


class LiveChatMessage(models.Model):
    """
    Real-time chat messages during live sessions.
    """
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('emoji', 'Emoji'),
        ('file', 'File'),
        ('system', 'System'),
    ]
    
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='chat_messages'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='live_chat_messages'
    )
    
    # Message content
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    file_url = models.URLField(blank=True)
    
    # Metadata
    is_pinned = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    
    # Reply/Thread
    reply_to = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies'
    )
    
    # Reactions
    likes_count = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['is_pinned']),
        ]
    
    def __str__(self):
        username = self.user.email if self.user else 'System'
        return f"{username}: {self.content[:50]}"


class LiveQuestion(models.Model):
    """
    Q&A questions during live sessions.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('answered', 'Answered'),
        ('dismissed', 'Dismissed'),
    ]
    
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='live_questions'
    )
    
    # Question
    question = models.TextField()
    answer = models.TextField(blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_anonymous = models.BooleanField(default=False)
    
    # Engagement
    upvotes = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    
    # Response tracking
    answered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='answered_questions'
    )
    answered_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-upvotes', '-created_at']
        indexes = [
            models.Index(fields=['session', 'status']),
            models.Index(fields=['user']),
            models.Index(fields=['-upvotes']),
        ]
    
    def __str__(self):
        return f"{self.question[:50]} - {self.status}"


class LivePoll(models.Model):
    """
    Interactive polls during live sessions.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    ]
    
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='polls'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_polls'
    )
    
    # Poll details
    question = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    
    # Settings
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    allow_multiple_answers = models.BooleanField(default=False)
    show_results_immediately = models.BooleanField(default=True)
    is_anonymous = models.BooleanField(default=False)
    
    # Duration
    duration_seconds = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(10)]
    )
    started_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session', 'status']),
        ]
    
    def __str__(self):
        return f"{self.question} - {self.status}"
    
    def total_votes(self):
        """Get total number of votes."""
        return self.votes.count()
    
    def is_active(self):
        """Check if poll is currently active."""
        if self.status != 'active':
            return False
        if self.ends_at and timezone.now() > self.ends_at:
            return False
        return True


class PollOption(models.Model):
    """
    Poll answer options.
    """
    poll = models.ForeignKey(
        LivePoll,
        on_delete=models.CASCADE,
        related_name='options'
    )
    
    text = models.CharField(max_length=255)
    order = models.IntegerField(default=0)
    
    # Denormalized count for performance
    votes_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order']
        indexes = [
            models.Index(fields=['poll', 'order']),
        ]
    
    def __str__(self):
        return f"{self.text} ({self.votes_count} votes)"
    
    def vote_percentage(self):
        """Get percentage of votes for this option."""
        total = self.poll.total_votes()
        if total == 0:
            return 0
        return round((self.votes_count / total) * 100, 1)


class PollVote(models.Model):
    """
    User votes on poll options.
    """
    poll = models.ForeignKey(
        LivePoll,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    option = models.ForeignKey(
        PollOption,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='poll_votes'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['poll', 'user']),
            models.Index(fields=['option']),
        ]
    
    def __str__(self):
        return f"{self.user.email} voted for {self.option.text}"


class SessionRecording(models.Model):
    """
    Recordings of live sessions.
    """
    PROCESSING_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('ready', 'Ready'),
        ('failed', 'Failed'),
    ]
    
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='recordings'
    )
    
    # Recording details
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # File information
    video_url = models.URLField()
    thumbnail_url = models.URLField(blank=True)
    duration_seconds = models.IntegerField(default=0)
    file_size_mb = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Processing
    processing_status = models.CharField(
        max_length=20,
        choices=PROCESSING_STATUS,
        default='pending'
    )
    error_message = models.TextField(blank=True)
    
    # Access control
    is_public = models.BooleanField(default=False)
    requires_enrollment = models.BooleanField(default=True)
    
    # Analytics
    views_count = models.IntegerField(default=0)
    downloads_count = models.IntegerField(default=0)
    
    # Timestamps
    recorded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['processing_status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.processing_status}"
    
    def duration_formatted(self):
        """Get formatted duration string."""
        hours = self.duration_seconds // 3600
        minutes = (self.duration_seconds % 3600) // 60
        seconds = self.duration_seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


class RecordingView(models.Model):
    """
    Tracks recording views and watch time.
    """
    recording = models.ForeignKey(
        SessionRecording,
        on_delete=models.CASCADE,
        related_name='views'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recording_views'
    )
    
    # Watch tracking
    watch_duration_seconds = models.IntegerField(default=0)
    last_position_seconds = models.IntegerField(default=0)
    completed = models.BooleanField(default=False)
    
    # Device info
    device_type = models.CharField(max_length=50, blank=True)
    browser = models.CharField(max_length=50, blank=True)
    
    # Timestamps
    first_viewed_at = models.DateTimeField(auto_now_add=True)
    last_viewed_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['recording', 'user']
        indexes = [
            models.Index(fields=['recording']),
            models.Index(fields=['user']),
            models.Index(fields=['completed']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.recording.title}"
    
    def watch_percentage(self):
        """Calculate watch percentage."""
        if self.recording.duration_seconds == 0:
            return 0
        return min(100, int((self.watch_duration_seconds / self.recording.duration_seconds) * 100))


class SessionAttendance(models.Model):
    """
    Attendance records for live sessions.
    Used for certification and completion tracking.
    """
    session = models.ForeignKey(
        LiveSession,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    participant = models.ForeignKey(
        SessionParticipant,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    
    # Attendance validation
    marked_present = models.BooleanField(default=False)
    attendance_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Verification
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_attendances'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['session', 'participant']
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['marked_present']),
        ]
    
    def __str__(self):
        status = "Present" if self.marked_present else "Absent"
        return f"{self.participant.user.email} - {status}"
