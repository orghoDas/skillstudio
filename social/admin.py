from django.contrib import admin
from .models import (
    Review, ReviewHelpful, Forum, Thread, Post, PostVote,
    LearningCircle, CircleMembership, CircleMessage,
    CircleGoal, CircleEvent, CircleResource
)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['course', 'user', 'rating', 'helpful_count', 'is_approved', 'is_flagged', 'created_at']
    list_filter = ['rating', 'is_approved', 'is_flagged', 'created_at']
    search_fields = ['course__title', 'user__username', 'title', 'comment']
    readonly_fields = ['helpful_count', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Review Information', {
            'fields': ('course', 'user', 'rating', 'title', 'comment')
        }),
        ('Status', {
            'fields': ('is_approved', 'is_flagged', 'helpful_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ['review', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review__title', 'user__username']


@admin.register(Forum)
class ForumAdmin(admin.ModelAdmin):
    list_display = ['title', 'course', 'is_locked', 'created_at']
    list_filter = ['is_locked', 'created_at']
    search_fields = ['title', 'description', 'course__title']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Forum Information', {
            'fields': ('title', 'description', 'course')
        }),
        ('Status', {
            'fields': ('is_locked',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ['title', 'forum', 'created_by', 'view_count', 'is_pinned', 'is_locked', 'created_at']
    list_filter = ['is_pinned', 'is_locked', 'is_solved', 'created_at']
    search_fields = ['title', 'content', 'created_by__username']
    readonly_fields = ['view_count', 'created_at', 'updated_at']
    filter_horizontal = []
    
    fieldsets = (
        ('Thread Information', {
            'fields': ('forum', 'title', 'content', 'created_by', 'tags')
        }),
        ('Status & Stats', {
            'fields': ('is_pinned', 'is_locked', 'is_solved', 'view_count')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['thread', 'user', 'upvotes', 'is_answer', 'created_at']
    list_filter = ['is_answer', 'created_at']
    search_fields = ['thread__title', 'user__username', 'content']
    readonly_fields = ['upvotes', 'created_at', 'edited_at']
    
    fieldsets = (
        ('Post Information', {
            'fields': ('thread', 'user', 'content', 'parent')
        }),
        ('Status & Stats', {
            'fields': ('is_answer', 'upvotes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(PostVote)
class PostVoteAdmin(admin.ModelAdmin):
    list_display = ['post', 'user', 'vote', 'created_at']
    list_filter = ['vote', 'created_at']
    search_fields = ['post__content', 'user__username']


@admin.register(LearningCircle)
class LearningCircleAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'created_by', 'member_count', 'max_members', 'is_private', 'status', 'created_at']
    list_filter = ['is_private', 'status', 'created_at']
    search_fields = ['name', 'description', 'created_by__username']
    readonly_fields = ['join_code', 'created_at']
    
    def member_count(self, obj):
        return CircleMembership.objects.filter(circle=obj, status='active').count()
    member_count.short_description = 'Members'
    
    fieldsets = (
        ('Circle Information', {
            'fields': ('name', 'description', 'course', 'created_by', 'cover_image')
        }),
        ('Settings', {
            'fields': ('max_members', 'is_private', 'join_code', 'status')
        }),
        ('Goals', {
            'fields': ('learning_goal', 'weekly_target_hours')
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        }),
    )


@admin.register(CircleMembership)
class CircleMembershipAdmin(admin.ModelAdmin):
    list_display = ['circle', 'user', 'role', 'status', 'joined_at', 'left_at']
    list_filter = ['role', 'status', 'joined_at']
    search_fields = ['circle__name', 'user__username']
    readonly_fields = ['joined_at', 'left_at']


@admin.register(CircleMessage)
class CircleMessageAdmin(admin.ModelAdmin):
    list_display = ['circle', 'user', 'message_preview', 'reply_to', 'created_at']
    list_filter = ['created_at']
    search_fields = ['circle__name', 'user__username', 'message']
    readonly_fields = ['created_at']
    
    def message_preview(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_preview.short_description = 'Message'


@admin.register(CircleGoal)
class CircleGoalAdmin(admin.ModelAdmin):
    list_display = ['circle', 'title', 'start_date', 'end_date', 'status', 'created_at']
    list_filter = ['status', 'start_date', 'end_date']
    search_fields = ['circle__name', 'title', 'description']
    readonly_fields = ['created_at']


@admin.register(CircleEvent)
class CircleEventAdmin(admin.ModelAdmin):
    list_display = ['circle', 'title', 'scheduled_at', 'created_by', 'created_at']
    list_filter = ['scheduled_at', 'created_at']
    search_fields = ['circle__name', 'title', 'description']
    readonly_fields = ['created_at']


@admin.register(CircleResource)
class CircleResourceAdmin(admin.ModelAdmin):
    list_display = ['circle', 'title', 'resource_type', 'shared_by', 'created_at']
    list_filter = ['resource_type', 'created_at']
    search_fields = ['circle__name', 'title', 'description']
    readonly_fields = ['created_at']

