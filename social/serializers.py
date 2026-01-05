from rest_framework import serializers
from .models import (
    Review, ReviewHelpful, Forum, Thread, Post, PostVote,
    LearningCircle, CircleMembership, CircleMessage,
    CircleGoal, CircleEvent, CircleResource
)
from accounts.serializers import UserBasicSerializer


# ===========================
# Reviews
# ===========================

class ReviewSerializer(serializers.ModelSerializer):
    """Review serializer."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = Review
        fields = [
            'id', 'user', 'user_name', 'course', 'course_title',
            'rating', 'title', 'comment', 'helpful_count',
            'is_approved', 'created_at', 'updated_at'
        ]
        read_only_fields = ['user', 'helpful_count', 'created_at', 'updated_at']


# ===========================
# Forums
# ===========================

class ForumSerializer(serializers.ModelSerializer):
    """Forum serializer."""
    thread_count = serializers.IntegerField(read_only=True)
    post_count = serializers.IntegerField(read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Forum
        fields = [
            'id', 'course', 'title', 'description', 'created_by',
            'created_by_name', 'created_at', 'is_locked', 'is_pinned',
            'thread_count', 'post_count'
        ]
        read_only_fields = ['created_by', 'created_at']


class ThreadSerializer(serializers.ModelSerializer):
    """Thread serializer."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    post_count = serializers.IntegerField(read_only=True)
    last_activity = serializers.DateTimeField(read_only=True)
    
    class Meta:
        model = Thread
        fields = [
            'id', 'forum', 'title', 'content', 'created_by', 'created_by_name',
            'created_at', 'updated_at', 'view_count', 'is_locked',
            'is_pinned', 'is_solved', 'tags', 'post_count', 'last_activity'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'view_count']


class PostSerializer(serializers.ModelSerializer):
    """Post serializer."""
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = Post
        fields = [
            'id', 'thread', 'user', 'user_name', 'content', 'parent',
            'is_answer', 'is_edited', 'created_at', 'edited_at', 'upvotes'
        ]
        read_only_fields = ['user', 'created_at', 'upvotes']


# ===========================
# Learning Circles
# ===========================

class LearningCircleSerializer(serializers.ModelSerializer):
    """Learning circle serializer."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    member_count = serializers.SerializerMethodField()
    is_full = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    
    class Meta:
        model = LearningCircle
        fields = [
            'id', 'name', 'description', 'course', 'max_members',
            'is_private', 'join_code', 'learning_goal', 'weekly_target_hours',
            'status', 'cover_image', 'created_by', 'created_by_name',
            'created_at', 'member_count', 'is_full', 'is_member'
        ]
        read_only_fields = ['created_by', 'created_at']
    
    def get_member_count(self, obj):
        """Get the member count from annotation or calculate it."""
        return obj.get_member_count()
    
    def get_is_full(self, obj):
        """Check if the circle is full."""
        return obj.is_full()
    
    def get_is_member(self, obj):
        """Check if the current user is a member of this circle."""
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            from .models import CircleMembership
            return CircleMembership.objects.filter(
                circle=obj,
                user=request.user,
                status='active'
            ).exists()
        return False


class LearningCircleDetailSerializer(LearningCircleSerializer):
    """Detailed learning circle serializer with members list."""
    members = serializers.SerializerMethodField()
    
    class Meta(LearningCircleSerializer.Meta):
        fields = LearningCircleSerializer.Meta.fields + ['members']
    
    def get_members(self, obj):
        """Get active members of the circle."""
        from .models import CircleMembership
        memberships = CircleMembership.objects.filter(
            circle=obj,
            status='active'
        ).select_related('user')
        
        return [{
            'id': m.user.id,
            'email': m.user.email,
            'first_name': getattr(m.user, 'first_name', ''),
            'last_name': getattr(m.user, 'last_name', ''),
            'role': m.role,
            'joined_at': m.joined_at
        } for m in memberships]


class CircleMembershipSerializer(serializers.ModelSerializer):
    """Circle membership serializer."""
    user = UserBasicSerializer(read_only=True)
    circle_name = serializers.CharField(source='circle.name', read_only=True)
    
    class Meta:
        model = CircleMembership
        fields = [
            'id', 'circle', 'circle_name', 'user', 'role',
            'status', 'joined_at', 'left_at'
        ]
        read_only_fields = ['joined_at']


class CircleMessageSerializer(serializers.ModelSerializer):
    """Circle message serializer."""
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = CircleMessage
        fields = [
            'id', 'circle', 'user', 'message', 'attachment',
            'reply_to', 'created_at', 'edited_at', 'is_edited'
        ]
        read_only_fields = ['user', 'created_at']


class CircleGoalSerializer(serializers.ModelSerializer):
    """Circle goal serializer."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = CircleGoal
        fields = [
            'id', 'circle', 'title', 'description', 'start_date',
            'end_date', 'status', 'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['created_by', 'created_at']


class CircleEventSerializer(serializers.ModelSerializer):
    """Circle event serializer."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = CircleEvent
        fields = [
            'id', 'circle', 'title', 'description', 'scheduled_at',
            'duration_minutes', 'meeting_link', 'created_by',
            'created_by_name', 'created_at'
        ]
        read_only_fields = ['created_by', 'created_at']


class CircleResourceSerializer(serializers.ModelSerializer):
    """Circle resource serializer."""
    shared_by_name = serializers.CharField(source='shared_by.get_full_name', read_only=True)
    
    class Meta:
        model = CircleResource
        fields = [
            'id', 'circle', 'title', 'description', 'resource_type',
            'url', 'file', 'note_content', 'shared_by',
            'shared_by_name', 'created_at'
        ]
        read_only_fields = ['shared_by', 'created_at']
