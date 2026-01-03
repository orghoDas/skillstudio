from rest_framework import serializers
from django.utils import timezone

from .models import Event, EventRegistration, EventFeedback, EventAttendanceLog, EventResource
from accounts.serializers import UserBasicSerializer


class EventSerializer(serializers.ModelSerializer):
    """Full event serializer with all details."""
    host_name = serializers.CharField(source='host.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True, allow_null=True)
    seats_available = serializers.IntegerField(read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    attendee_count = serializers.IntegerField(read_only=True)
    is_past = serializers.BooleanField(read_only=True)
    is_upcoming = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Event
        fields = [
            'id', 'host', 'host_name', 'course', 'course_title',
            'title', 'description', 'event_type', 'cover_image',
            'scheduled_for', 'duration_minutes', 'timezone',
            'max_seats', 'price', 'is_free', 'requires_enrollment',
            'prerequisites', 'meeting_link', 'meeting_password', 'platform',
            'status', 'is_featured',
            'seats_available', 'is_full', 'attendee_count', 'is_past', 'is_upcoming',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'host']


class EventListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing events."""
    host_name = serializers.CharField(source='host.get_full_name', read_only=True)
    seats_available = serializers.IntegerField(read_only=True)
    attendee_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Event
        fields = [
            'id', 'title', 'event_type', 'host_name', 'cover_image',
            'scheduled_for', 'duration_minutes', 'max_seats',
            'price', 'is_free', 'status', 'is_featured',
            'seats_available', 'attendee_count'
        ]


class EventDetailSerializer(serializers.ModelSerializer):
    """Detailed event serializer for single event view."""
    host = UserBasicSerializer(read_only=True)
    registrations_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    user_registration = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'host', 'course', 'title', 'description', 'event_type',
            'cover_image', 'scheduled_for', 'duration_minutes', 'timezone',
            'max_seats', 'price', 'is_free', 'requires_enrollment',
            'prerequisites', 'platform', 'status', 'is_featured',
            'registrations_count', 'average_rating', 'user_registration',
            'created_at'
        ]
    
    def get_registrations_count(self, obj):
        return obj.registrations.filter(status='confirmed').count()
    
    def get_average_rating(self, obj):
        feedbacks = obj.feedbacks.all()
        if not feedbacks:
            return None
        return sum(f.rating for f in feedbacks) / len(feedbacks)
    
    def get_user_registration(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        reg = obj.registrations.filter(user=request.user).first()
        if reg:
            return EventRegistrationSerializer(reg).data
        return None


class EventRegistrationSerializer(serializers.ModelSerializer):
    """Event registration serializer."""
    event_title = serializers.CharField(source='event.title', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = EventRegistration
        fields = [
            'id', 'event', 'event_title', 'user', 'user_email',
            'payment_status', 'payment_amount', 'status',
            'attended', 'attended_at', 'registered_on', 'cancelled_at'
        ]
        read_only_fields = ['registered_on', 'user']


class EventFeedbackSerializer(serializers.ModelSerializer):
    """Event feedback serializer."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    event_title = serializers.CharField(source='event.title', read_only=True)
    
    class Meta:
        model = EventFeedback
        fields = [
            'id', 'event', 'event_title', 'user', 'user_name',
            'rating', 'title', 'comment', 'content_quality',
            'host_performance', 'would_recommend', 'created_at'
        ]
        read_only_fields = ['created_at', 'user']


class EventResourceSerializer(serializers.ModelSerializer):
    """Event resource serializer."""
    
    class Meta:
        model = EventResource
        fields = [
            'id', 'event', 'title', 'description', 'resource_type',
            'file', 'url', 'available_after_event', 'attendees_only',
            'uploaded_at'
        ]
        read_only_fields = ['uploaded_at']


class EventAttendanceLogSerializer(serializers.ModelSerializer):
    """Attendance log serializer."""
    
    class Meta:
        model = EventAttendanceLog
        fields = [
            'id', 'registration', 'joined_at', 'left_at',
            'duration_minutes', 'ip_address', 'user_agent'
        ]
        read_only_fields = ['joined_at']
