"""
Live Streaming Serializers
Serializers for live sessions, chat, polls, recordings, and attendance.
"""

from rest_framework import serializers
from django.utils import timezone
from live.models import (
    LiveSession, SessionParticipant, LiveChatMessage, LiveQuestion,
    LivePoll, PollOption, PollVote, SessionRecording, RecordingView,
    SessionAttendance
)
from accounts.models import User
from courses.models import Course


class LiveSessionSerializer(serializers.ModelSerializer):
    """Serializer for LiveSession model."""
    
    instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)
    instructor_email = serializers.CharField(source='instructor.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    
    duration_minutes = serializers.SerializerMethodField()
    participant_count = serializers.SerializerMethodField()
    available_slots = serializers.SerializerMethodField()
    is_upcoming = serializers.SerializerMethodField()
    is_live = serializers.SerializerMethodField()
    is_past = serializers.SerializerMethodField()
    
    class Meta:
        model = LiveSession
        fields = [
            'id', 'course', 'course_title', 'course_slug', 'instructor',
            'instructor_name', 'instructor_email', 'title', 'description',
            'session_type', 'scheduled_start', 'scheduled_end', 'actual_start',
            'actual_end', 'timezone_info', 'platform', 'meeting_link',
            'meeting_id', 'meeting_password', 'max_participants',
            'enable_chat', 'enable_qa', 'enable_polls', 'enable_recording',
            'enable_screen_share', 'requires_enrollment', 'is_public',
            'password_protected', 'status', 'is_featured', 'duration_minutes',
            'participant_count', 'available_slots', 'is_upcoming', 'is_live',
            'is_past', 'is_streaming', 'stream_type', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'instructor', 'actual_start', 'actual_end', 'status',
            'created_at', 'updated_at'
        ]
    
    def get_duration_minutes(self, obj):
        return obj.duration_minutes()
    
    def get_participant_count(self, obj):
        # Use annotated count if available, otherwise call method
        return getattr(obj, 'participants_joined', obj.participant_count())
    
    def get_available_slots(self, obj):
        return obj.available_slots()
    
    def get_is_upcoming(self, obj):
        return obj.is_upcoming()
    
    def get_is_live(self, obj):
        return obj.is_live()
    
    def get_is_past(self, obj):
        return obj.is_past()


class CreateLiveSessionSerializer(serializers.ModelSerializer):
    """Serializer for creating live sessions."""
    
    class Meta:
        model = LiveSession
        fields = [
            'course', 'title', 'description', 'session_type',
            'scheduled_start', 'scheduled_end', 'timezone_info',
            'platform', 'meeting_link', 'meeting_id', 'meeting_password',
            'max_participants', 'enable_chat', 'enable_qa', 'enable_polls',
            'enable_recording', 'enable_screen_share', 'requires_enrollment',
            'is_public', 'password_protected'
        ]
    
    def validate(self, data):
        """Validate session schedule."""
        if data['scheduled_start'] >= data['scheduled_end']:
            raise serializers.ValidationError(
                "Start time must be before end time"
            )
        
        if data['scheduled_start'] < timezone.now():
            raise serializers.ValidationError(
                "Cannot schedule session in the past"
            )
        
        return data


class SessionParticipantSerializer(serializers.ModelSerializer):
    """Serializer for SessionParticipant model."""
    
    user_name = serializers.SerializerMethodField()
    user_email = serializers.CharField(source='user.email', read_only=True)
    session_title = serializers.CharField(source='session.title', read_only=True)
    attendance_rate = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = SessionParticipant
        fields = [
            'id', 'session', 'session_title', 'user', 'user_name',
            'user_email', 'status', 'joined_at', 'left_at',
            'duration_seconds', 'chat_messages_count', 'questions_asked',
            'polls_answered', 'can_unmute', 'can_share_screen',
            'is_moderator', 'attendance_rate', 'registered_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'duration_seconds', 'chat_messages_count',
            'questions_asked', 'polls_answered', 'registered_at', 'updated_at'
        ]
    
    def get_user_name(self, obj):
        """Get user's full name from profile if available."""
        try:
            if hasattr(obj.user, 'profile'):
                profile = obj.user.profile
                if profile:
                    full_name = f"{profile.first_name or ''} {profile.last_name or ''}".strip()
                    if full_name:
                        return full_name
            return obj.user.username or obj.user.email
        except Exception:
            return obj.user.email


class LiveChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for LiveChatMessage model."""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    reply_to_content = serializers.CharField(
        source='reply_to.content',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = LiveChatMessage
        fields = [
            'id', 'session', 'user', 'user_name', 'user_email',
            'message_type', 'content', 'file_url', 'is_pinned',
            'is_deleted', 'is_edited', 'reply_to', 'reply_to_content',
            'likes_count', 'created_at', 'edited_at', 'deleted_at'
        ]
        read_only_fields = [
            'id', 'user', 'is_deleted', 'is_edited', 'likes_count',
            'created_at', 'edited_at', 'deleted_at'
        ]


class SendChatMessageSerializer(serializers.Serializer):
    """Serializer for sending chat messages."""
    
    content = serializers.CharField(max_length=5000)
    message_type = serializers.ChoiceField(
        choices=['text', 'emoji', 'file'],
        default='text'
    )
    reply_to = serializers.IntegerField(required=False, allow_null=True)
    file_url = serializers.URLField(required=False, allow_blank=True)


class LiveQuestionSerializer(serializers.ModelSerializer):
    """Serializer for LiveQuestion model."""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    answered_by_name = serializers.CharField(
        source='answered_by.get_full_name',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = LiveQuestion
        fields = [
            'id', 'session', 'user', 'user_name', 'user_email',
            'question', 'answer', 'status', 'is_anonymous', 'upvotes',
            'is_featured', 'answered_by', 'answered_by_name', 'answered_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'user', 'upvotes', 'answered_by', 'answered_at',
            'created_at', 'updated_at'
        ]


class AskQuestionSerializer(serializers.Serializer):
    """Serializer for asking questions."""
    
    question = serializers.CharField(max_length=5000)
    is_anonymous = serializers.BooleanField(default=False)


class AnswerQuestionSerializer(serializers.Serializer):
    """Serializer for answering questions."""
    
    answer = serializers.CharField(max_length=10000)


class PollOptionSerializer(serializers.ModelSerializer):
    """Serializer for PollOption model."""
    
    vote_percentage = serializers.FloatField(read_only=True)
    
    class Meta:
        model = PollOption
        fields = ['id', 'poll', 'text', 'order', 'votes_count', 'vote_percentage']
        read_only_fields = ['id', 'poll', 'votes_count']


class LivePollSerializer(serializers.ModelSerializer):
    """Serializer for LivePoll model."""
    
    options = PollOptionSerializer(many=True, read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.get_full_name',
        read_only=True
    )
    total_votes = serializers.IntegerField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = LivePoll
        fields = [
            'id', 'session', 'created_by', 'created_by_name', 'question',
            'description', 'status', 'allow_multiple_answers',
            'show_results_immediately', 'is_anonymous', 'duration_seconds',
            'started_at', 'ends_at', 'options', 'total_votes', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_by', 'status', 'started_at', 'ends_at',
            'created_at', 'updated_at'
        ]


class CreatePollSerializer(serializers.Serializer):
    """Serializer for creating polls."""
    
    question = serializers.CharField(max_length=500)
    description = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    options = serializers.ListField(
        child=serializers.CharField(max_length=255),
        min_length=2,
        max_length=10
    )
    allow_multiple_answers = serializers.BooleanField(default=False)
    show_results_immediately = serializers.BooleanField(default=True)
    is_anonymous = serializers.BooleanField(default=False)
    duration_seconds = serializers.IntegerField(required=False, allow_null=True)


class VotePollSerializer(serializers.Serializer):
    """Serializer for voting on polls."""
    
    option_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        max_length=10
    )


class PollResultsSerializer(serializers.Serializer):
    """Serializer for poll results."""
    
    question = serializers.CharField()
    status = serializers.CharField()
    total_votes = serializers.IntegerField()
    options = serializers.ListField()


class SessionRecordingSerializer(serializers.ModelSerializer):
    """Serializer for SessionRecording model."""
    
    session_title = serializers.CharField(source='session.title', read_only=True)
    course_title = serializers.CharField(source='session.course.title', read_only=True)
    duration_formatted = serializers.CharField(read_only=True)
    
    class Meta:
        model = SessionRecording
        fields = [
            'id', 'session', 'session_title', 'course_title', 'title',
            'description', 'video_url', 'thumbnail_url', 'duration_seconds',
            'duration_formatted', 'file_size_mb', 'processing_status',
            'error_message', 'is_public', 'requires_enrollment',
            'views_count', 'downloads_count', 'recorded_at',
            'processed_at', 'published_at'
        ]
        read_only_fields = [
            'id', 'processing_status', 'error_message', 'views_count',
            'downloads_count', 'recorded_at', 'processed_at', 'published_at'
        ]


class CreateRecordingSerializer(serializers.ModelSerializer):
    """Serializer for creating recordings."""
    
    class Meta:
        model = SessionRecording
        fields = [
            'session', 'title', 'description', 'video_url',
            'thumbnail_url', 'duration_seconds', 'file_size_mb',
            'is_public', 'requires_enrollment'
        ]


class RecordingViewSerializer(serializers.ModelSerializer):
    """Serializer for RecordingView model."""
    
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    recording_title = serializers.CharField(source='recording.title', read_only=True)
    watch_percentage = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = RecordingView
        fields = [
            'id', 'recording', 'recording_title', 'user', 'user_name',
            'watch_duration_seconds', 'last_position_seconds', 'completed',
            'watch_percentage', 'device_type', 'browser', 'first_viewed_at',
            'last_viewed_at'
        ]
        read_only_fields = ['id', 'first_viewed_at', 'last_viewed_at']


class TrackRecordingViewSerializer(serializers.Serializer):
    """Serializer for tracking recording views."""
    
    watch_duration_seconds = serializers.IntegerField(min_value=0)
    last_position_seconds = serializers.IntegerField(min_value=0)
    device_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    browser = serializers.CharField(max_length=50, required=False, allow_blank=True)


class SessionAttendanceSerializer(serializers.ModelSerializer):
    """Serializer for SessionAttendance model."""
    
    user_name = serializers.CharField(source='participant.user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='participant.user.email', read_only=True)
    session_title = serializers.CharField(source='session.title', read_only=True)
    
    class Meta:
        model = SessionAttendance
        fields = [
            'id', 'session', 'session_title', 'participant', 'user_name',
            'user_email', 'marked_present', 'attendance_percentage',
            'verified_by', 'verified_at', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'verified_by', 'verified_at', 'created_at', 'updated_at'
        ]


class SessionAnalyticsSerializer(serializers.Serializer):
    """Serializer for session analytics data."""
    
    session = serializers.DictField()
    participation = serializers.DictField()
    engagement = serializers.DictField()
    recordings = serializers.DictField()


class JoinSessionSerializer(serializers.Serializer):
    """Serializer for joining a session."""
    
    meeting_password = serializers.CharField(max_length=100, required=False, allow_blank=True)
