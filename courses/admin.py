from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.urls import reverse
from django.utils.html import format_html
from accounts.utils import is_platform_admin
from core.admin import ReadOnlyAdmin, WorkflowAdmin
from .models import (
    Course, Category, Tag, Module, Lesson,
    CourseVersion, CourseTag, LessonResource
)
from .services import course_learner_count, transition


class LessonResourceInline(admin.TabularInline):
    model = LessonResource
    extra = 1
    fields = ('file_url', 'resource_type', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 1
    fields = ('title', 'content_type', 'position', 'is_free', 'duration_seconds')
    show_change_link = True


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1
    fields = ('title', 'position')
    show_change_link = True


class CourseTagInline(admin.TabularInline):
    model = CourseTag
    extra = 1


@admin.register(Course)
class CourseAdmin(WorkflowAdmin):
    decision_help = 'Use the record details to inspect the course before deciding. Returning it to draft requires feedback for the instructor.'

    def decision_details(self, obj):
        return [*super().decision_details(obj), ('Instructor', obj.instructor.email), ('Category', obj.category.name if obj.category else 'Uncategorized')]

    def workflow_choices(self, obj):
        if obj.status == 'under_review':
            return [('published', 'Publish course'), ('draft', 'Return to draft')]
        if obj.status == 'published':
            return [('archived', 'Archive course')]
        return []

    def apply_decision(self, request, obj, data):
        course = transition(obj, data['action'], request.user, reason=data['note'])
        return f'Course status changed to {course.get_status_display().lower()}.'

    list_display = (
        'title', 'instructor', 'category', 'status_badge', 
        'is_free', 'price', 'level', 'enrollment_count', 'created_at'
    )
    list_filter = ('status', 'is_free', 'level', 'category', 'created_at')
    search_fields = ('title', 'instructor__email', 'category__name', 'description')
    inlines = [ModuleInline, CourseTagInline]
    readonly_fields = (
        'created_at', 'updated_at', 'published_at', 'submitted_for_review_at',
        'reviewed_at', 'reviewed_by', 'archived_at', 'status', 'rejection_reason',
        'revision_of', 'current_version', 'content_editor',
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'thumbnail', 'instructor', 'category')
        }),
        ('Pricing', {
            'fields': ('price', 'is_free')
        }),
        ('Course Details', {
            'fields': ('level', 'status', 'revision_of', 'current_version', 'content_editor')
        }),
        ('Publishing Information', {
            'fields': (
                'submitted_for_review_at', 'published_at', 'reviewed_at',
                'reviewed_by', 'rejection_reason', 'archived_at'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'under_review': 'orange',
            'published': 'green',
            'archived': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('instructor', 'category').annotate(
            learner_count=course_learner_count(),
        )

    def enrollment_count(self, obj):
        return obj.learner_count
    enrollment_count.short_description = 'Enrollments'
    
    actions = ['publish_courses', 'archive_courses']

    def has_moderate_permission(self, request):
        return is_platform_admin(request.user) and request.user.has_perm('courses.change_course')

    @admin.display(description='Course editor')
    def content_editor(self, obj):
        return format_html('<a href="{}">Manage course content</a>', reverse('instructor_course_content', args=[obj.slug]))
    
    @admin.action(permissions=['moderate'], description='Publish selected courses')
    def publish_courses(self, request, queryset):
        self._transition_courses(request, queryset, 'published')

    @admin.action(permissions=['moderate'], description='Archive selected courses')
    def archive_courses(self, request, queryset):
        self._transition_courses(request, queryset, 'archived')

    def _transition_courses(self, request, queryset, to_state):
        updated = skipped = 0
        for course in queryset:
            try:
                with transaction.atomic():
                    transition(course, to_state, request.user)
                    self.log_change(request, course, f'Course {to_state}.')
            except (ValidationError, Http404):
                skipped += 1
            else:
                updated += 1
        self.message_user(request, f'{updated} course(s) {to_state}.')
        if skipped:
            self.message_user(
                request, f'Skipped {skipped} course(s) in an ineligible status.', messages.WARNING
            )


@admin.register(Module)
class ModuleAdmin(ReadOnlyAdmin):
    list_display = ('title', 'course', 'position', 'lesson_count', 'created_at')
    list_filter = ('course', 'created_at')
    search_fields = ('title', 'course__title')
    inlines = [LessonInline]
    
    def lesson_count(self, obj):
        return obj.lessons.count()
    lesson_count.short_description = 'Lessons'


@admin.register(Lesson)
class LessonAdmin(ReadOnlyAdmin):
    list_display = (
        'title', 'module', 'content_type', 'position', 
        'is_free', 'duration_seconds', 'view_count', 'created_at'
    )
    list_filter = ('content_type', 'is_free', 'module__course', 'created_at')
    search_fields = ('title', 'module__title', 'module__course__title')
    inlines = [LessonResourceInline]
    readonly_fields = ('view_count', 'created_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('module', 'title', 'content_type', 'position', 'is_free')
        }),
        ('Content', {
            'fields': ('content_text', 'video_url', 'duration_seconds', 'metadata')
        }),
        ('Statistics', {
            'fields': ('view_count', 'created_at')
        }),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'course_count')
    search_fields = ('name',)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(total_courses=Count('courses'))

    @admin.display(ordering='total_courses', description='Courses')
    def course_count(self, obj):
        return obj.total_courses


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_count')
    search_fields = ('name',)
    
    def course_count(self, obj):
        return obj.coursetag_set.count()
    course_count.short_description = 'Courses'


@admin.register(LessonResource)
class LessonResourceAdmin(ReadOnlyAdmin):
    list_display = ('lesson', 'resource_type', 'uploaded_at')
    list_filter = ('resource_type', 'uploaded_at')
    search_fields = ('lesson__title',)
    readonly_fields = ('uploaded_at',)


@admin.register(CourseVersion)
class CourseVersionAdmin(ReadOnlyAdmin):
    list_display = ('course', 'version_number', 'created_at')
    list_filter = ('course', 'created_at')
    search_fields = ('course__title',)
    readonly_fields = ('created_at',)


admin.site.register(CourseTag, ReadOnlyAdmin)
