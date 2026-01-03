from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Skill, CourseSkill, UserSkill, UserInterest,
    Recommendation, SkillGapAnalysis, TrendingSkill,
    LearningPath, PathCourse, UserLearningPath
)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    """Admin interface for Skill model"""
    
    list_display = ['name', 'category', 'popularity_score', 'learner_count_display', 'is_active', 'created_at']
    list_filter = ['category', 'is_active', 'created_at']
    search_fields = ['name', 'slug', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['popularity_score', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'category', 'description')
        }),
        ('Status', {
            'fields': ('is_active', 'popularity_score')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def learner_count_display(self, obj):
        count = obj.learner_count
        return format_html('<strong>{}</strong>', count)
    learner_count_display.short_description = 'Learners'


@admin.register(CourseSkill)
class CourseSkillAdmin(admin.ModelAdmin):
    """Admin interface for CourseSkill model"""
    
    list_display = ['course', 'skill', 'weight', 'is_primary', 'added_by', 'created_at']
    list_filter = ['is_primary', 'added_by', 'skill__category', 'created_at']
    search_fields = ['course__title', 'skill__name']
    raw_id_fields = ['course', 'skill']
    readonly_fields = ['created_at']
    
    list_per_page = 50


@admin.register(UserSkill)
class UserSkillAdmin(admin.ModelAdmin):
    """Admin interface for UserSkill model"""
    
    list_display = ['user', 'skill', 'proficiency_display', 'source', 'last_practiced_at']
    list_filter = ['source', 'skill__category', 'first_learned_at']
    search_fields = ['user__email', 'skill__name']
    raw_id_fields = ['user', 'skill']
    readonly_fields = ['first_learned_at', 'last_practiced_at']
    
    date_hierarchy = 'last_practiced_at'
    list_per_page = 50
    
    def proficiency_display(self, obj):
        color = '#28a745' if obj.proficiency >= 70 else '#ffc107' if obj.proficiency >= 40 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, obj.proficiency
        )
    proficiency_display.short_description = 'Proficiency'


@admin.register(UserInterest)
class UserInterestAdmin(admin.ModelAdmin):
    """Admin interface for UserInterest model"""
    
    list_display = ['user', 'skill', 'interest_level', 'reason', 'target_proficiency', 'deadline', 'created_at']
    list_filter = ['reason', 'created_at']
    search_fields = ['user__email', 'skill__name']
    raw_id_fields = ['user', 'skill']
    readonly_fields = ['created_at', 'updated_at']
    
    date_hierarchy = 'created_at'


@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    """Admin interface for Recommendation model"""
    
    list_display = ['user', 'course', 'score_display', 'algorithm', 'status_display', 'clicked', 'created_at']
    list_filter = ['algorithm', 'status', 'clicked', 'created_at']
    search_fields = ['user__email', 'course__title']
    raw_id_fields = ['user', 'course']
    filter_horizontal = ['matched_skills']
    readonly_fields = ['clicked_at', 'created_at']
    
    date_hierarchy = 'created_at'
    list_per_page = 50
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'course', 'score', 'algorithm')
        }),
        ('Details', {
            'fields': ('reason', 'matched_skills', 'metadata')
        }),
        ('Status', {
            'fields': ('status', 'clicked', 'clicked_at', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('model_version', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    def score_display(self, obj):
        color = '#28a745' if obj.score >= 70 else '#ffc107' if obj.score >= 40 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}</span>',
            color, obj.score
        )
    score_display.short_description = 'Score'
    
    def status_display(self, obj):
        colors = {
            'active': '#28a745',
            'dismissed': '#6c757d',
            'enrolled': '#007bff',
            'expired': '#dc3545',
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#000'),
            obj.get_status_display()
        )
    status_display.short_description = 'Status'


@admin.register(SkillGapAnalysis)
class SkillGapAnalysisAdmin(admin.ModelAdmin):
    """Admin interface for SkillGapAnalysis model"""
    
    list_display = ['user', 'target_role', 'gap_score_display', 'progress_display', 'estimated_learning_hours', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['user__email', 'target_role']
    raw_id_fields = ['user']
    filter_horizontal = ['target_skills']
    readonly_fields = ['created_at', 'updated_at', 'last_analyzed_at']
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'target_role', 'target_skills')
        }),
        ('Analysis Results', {
            'fields': ('gap_score', 'priority_skills', 'estimated_learning_hours')
        }),
        ('Progress', {
            'fields': ('is_active', 'progress')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_analyzed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def gap_score_display(self, obj):
        color = '#28a745' if obj.gap_score <= 30 else '#ffc107' if obj.gap_score <= 60 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, obj.gap_score
        )
    gap_score_display.short_description = 'Gap Score'
    
    def progress_display(self, obj):
        color = '#28a745' if obj.progress >= 70 else '#ffc107' if obj.progress >= 40 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, obj.progress
        )
    progress_display.short_description = 'Progress'


@admin.register(TrendingSkill)
class TrendingSkillAdmin(admin.ModelAdmin):
    """Admin interface for TrendingSkill model"""
    
    list_display = ['skill', 'rank_display', 'rank_change_display', 'period_type', 'period_end', 'enrollment_count', 'trend_score']
    list_filter = ['period_type', 'period_end']
    search_fields = ['skill__name']
    raw_id_fields = ['skill']
    readonly_fields = ['created_at']
    
    date_hierarchy = 'period_end'
    list_per_page = 50
    
    def rank_display(self, obj):
        if obj.rank <= 3:
            color = '#ffd700'  # Gold
        elif obj.rank <= 10:
            color = '#c0c0c0'  # Silver
        else:
            color = '#000'
        return format_html(
            '<span style="color: {}; font-weight: bold;">#{}</span>',
            color, obj.rank
        )
    rank_display.short_description = 'Rank'
    
    def rank_change_display(self, obj):
        if obj.rank_change > 0:
            return format_html(
                '<span style="color: #28a745;">▲ {}</span>',
                obj.rank_change
            )
        elif obj.rank_change < 0:
            return format_html(
                '<span style="color: #dc3545;">▼ {}</span>',
                abs(obj.rank_change)
            )
        else:
            return format_html('<span>—</span>')
    rank_change_display.short_description = 'Change'


@admin.register(LearningPath)
class LearningPathAdmin(admin.ModelAdmin):
    """Admin interface for LearningPath model"""
    
    list_display = ['title', 'difficulty_level', 'is_official', 'is_published', 'enrollment_count', 'completion_rate_display', 'created_at']
    list_filter = ['difficulty_level', 'is_official', 'is_published', 'created_at']
    search_fields = ['title', 'description', 'target_role']
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ['created_by']
    filter_horizontal = ['required_skills']
    readonly_fields = ['enrollment_count', 'completion_count', 'avg_rating', 'created_at', 'updated_at']
    
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'target_role', 'difficulty_level')
        }),
        ('Skills & Courses', {
            'fields': ('required_skills',)
        }),
        ('Estimates', {
            'fields': ('estimated_hours', 'estimated_weeks')
        }),
        ('Curation', {
            'fields': ('created_by', 'is_official', 'is_published')
        }),
        ('Statistics', {
            'fields': ('enrollment_count', 'completion_count', 'avg_rating'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def completion_rate_display(self, obj):
        rate = obj.completion_rate
        color = '#28a745' if rate >= 70 else '#ffc107' if rate >= 40 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, rate
        )
    completion_rate_display.short_description = 'Completion Rate'


class PathCourseInline(admin.TabularInline):
    """Inline for courses in learning path"""
    model = PathCourse
    extra = 1
    raw_id_fields = ['course']


@admin.register(PathCourse)
class PathCourseAdmin(admin.ModelAdmin):
    """Admin interface for PathCourse model"""
    
    list_display = ['learning_path', 'course', 'order', 'is_required']
    list_filter = ['is_required']
    search_fields = ['learning_path__title', 'course__title']
    raw_id_fields = ['learning_path', 'course']
    
    list_per_page = 50


@admin.register(UserLearningPath)
class UserLearningPathAdmin(admin.ModelAdmin):
    """Admin interface for UserLearningPath model"""
    
    list_display = ['user', 'learning_path', 'progress_display', 'started_at', 'completed_at', 'target_completion_date']
    list_filter = ['started_at', 'completed_at']
    search_fields = ['user__email', 'learning_path__title']
    raw_id_fields = ['user', 'learning_path']
    filter_horizontal = ['completed_courses']
    readonly_fields = ['started_at', 'completed_at']
    
    date_hierarchy = 'started_at'
    list_per_page = 50
    
    def progress_display(self, obj):
        color = '#28a745' if obj.progress >= 70 else '#ffc107' if obj.progress >= 40 else '#dc3545'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
            color, obj.progress
        )
    progress_display.short_description = 'Progress'
