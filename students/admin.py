from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import StudentProfile, StudentNote, StudentBookmark


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'preferred_learning_style',
        'weekly_study_hours',
        'courses_stats',
        'watch_time_hours',
        'created_at',
    ]
    list_filter = [
        'preferred_learning_style',
        'preferred_study_time',
        'created_at',
    ]
    search_fields = [
        'user__email',
        'user__username',
        'learning_goals',
    ]
    readonly_fields = [
        'id',
        'total_courses_enrolled',
        'total_courses_completed',
        'total_certificates_earned',
        'total_watch_time',
        'created_at',
        'updated_at',
    ]
    fieldsets = (
        ('User', {
            'fields': ('id', 'user')
        }),
        ('Learning Preferences', {
            'fields': (
                'preferred_learning_style',
                'learning_goals',
                'interests',
                'weekly_study_hours',
                'preferred_study_time',
            )
        }),
        ('Statistics', {
            'fields': (
                'total_courses_enrolled',
                'total_courses_completed',
                'total_certificates_earned',
                'total_watch_time',
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def user_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    
    def courses_stats(self, obj):
        return format_html(
            '{} / {} completed',
            obj.total_courses_completed,
            obj.total_courses_enrolled
        )
    courses_stats.short_description = 'Courses'
    
    def watch_time_hours(self, obj):
        hours = obj.total_watch_time / 3600
        return f"{hours:.1f}h"
    watch_time_hours.short_description = 'Watch Time'


@admin.register(StudentNote)
class StudentNoteAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'lesson_link',
        'content_preview',
        'timestamp_display',
        'is_pinned',
        'created_at',
    ]
    list_filter = [
        'is_pinned',
        'created_at',
    ]
    search_fields = [
        'user__email',
        'lesson__title',
        'content',
    ]
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        ('Note Information', {
            'fields': ('id', 'user', 'lesson')
        }),
        ('Content', {
            'fields': ('content', 'timestamp', 'tags')
        }),
        ('Organization', {
            'fields': ('is_pinned',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def user_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    
    def lesson_link(self, obj):
        url = reverse('admin:courses_lesson_change', args=[obj.lesson.id])
        return format_html('<a href="{}">{}</a>', url, obj.lesson.title)
    lesson_link.short_description = 'Lesson'
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
    
    def timestamp_display(self, obj):
        minutes = obj.timestamp // 60
        seconds = obj.timestamp % 60
        return f"{minutes}:{seconds:02d}"
    timestamp_display.short_description = 'Timestamp'


@admin.register(StudentBookmark)
class StudentBookmarkAdmin(admin.ModelAdmin):
    list_display = [
        'user_link',
        'bookmark_type',
        'content_link',
        'created_at',
    ]
    list_filter = ['created_at']
    search_fields = [
        'user__email',
        'course__title',
        'lesson__title',
        'note',
    ]
    readonly_fields = ['id', 'created_at']
    fieldsets = (
        ('Bookmark Information', {
            'fields': ('id', 'user')
        }),
        ('Bookmarked Content', {
            'fields': ('course', 'lesson', 'note')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def user_link(self, obj):
        url = reverse('admin:accounts_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.email)
    user_link.short_description = 'User'
    
    def bookmark_type(self, obj):
        if obj.lesson:
            return 'Lesson'
        return 'Course'
    bookmark_type.short_description = 'Type'
    
    def content_link(self, obj):
        if obj.lesson:
            url = reverse('admin:courses_lesson_change', args=[obj.lesson.id])
            return format_html('<a href="{}">{}</a>', url, obj.lesson.title)
        elif obj.course:
            url = reverse('admin:courses_course_change', args=[obj.course.id])
            return format_html('<a href="{}">{}</a>', url, obj.course.title)
        return '-'
    content_link.short_description = 'Content'
