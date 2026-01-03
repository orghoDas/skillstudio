from django.contrib import admin
from .models import (
    CourseAnalyticsSnapshot,
    UserInteraction,
    InstructorAnalytics,
    LessonAnalytics,
    EventAnalytics,
    SearchQuery,
    DailyPlatformMetrics,
)


@admin.register(CourseAnalyticsSnapshot)
class CourseAnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ['course', 'snapshot_date', 'total_enrollments', 'total_completions', 'total_revenue']
    list_filter = ['snapshot_date']
    search_fields = ['course__title']
    readonly_fields = ['created_at']
    date_hierarchy = 'snapshot_date'


@admin.register(UserInteraction)
class UserInteractionAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'course', 'event', 'created_at']
    list_filter = ['action', 'created_at']
    search_fields = ['user__email', 'session_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(InstructorAnalytics)
class InstructorAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['instructor', 'total_courses', 'total_students', 'total_revenue', 'average_rating', 'last_updated']
    search_fields = ['instructor__email']
    readonly_fields = ['last_updated']


@admin.register(LessonAnalytics)
class LessonAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'total_views', 'total_completions', 'drop_off_rate', 'last_updated']
    search_fields = ['lesson__title']
    readonly_fields = ['last_updated']


@admin.register(EventAnalytics)
class EventAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['event', 'total_registrations', 'total_attendees', 'attendance_rate', 'total_revenue']
    search_fields = ['event__title']
    readonly_fields = ['last_updated']


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ['query', 'user', 'results_count', 'clicked_result', 'created_at']
    list_filter = ['created_at']
    search_fields = ['query']
    readonly_fields = ['created_at']
    date_hierarchy = 'created_at'


@admin.register(DailyPlatformMetrics)
class DailyPlatformMetricsAdmin(admin.ModelAdmin):
    list_display = ['date', 'total_users', 'new_users', 'active_users', 'total_enrollments', 'total_revenue']
    list_filter = ['date']
    readonly_fields = ['created_at']
    date_hierarchy = 'date'

