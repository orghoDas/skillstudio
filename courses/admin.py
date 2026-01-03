from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Course, Category, Tag, Module, Lesson,
    CourseVersion, CourseTag, LessonResource
)
from social.models import Review


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
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'instructor', 'category', 'status_badge', 
        'is_free', 'price', 'level', 'enrollment_count', 'created_at'
    )
    list_filter = ('status', 'is_free', 'level', 'category', 'created_at')
    search_fields = ('title', 'instructor__email', 'category__name', 'description')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ModuleInline, CourseTagInline]
    readonly_fields = (
        'created_at', 'updated_at', 'published_at', 'submitted_for_review_at',
        'reviewed_at', 'reviewed_by', 'archived_at'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'description', 'thumbnail', 'instructor', 'category')
        }),
        ('Pricing', {
            'fields': ('price', 'is_free')
        }),
        ('Course Details', {
            'fields': ('level', 'status')
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
    
    def enrollment_count(self, obj):
        return obj.enrollments.filter(status='active').count()
    enrollment_count.short_description = 'Enrollments'
    
    actions = ['publish_courses', 'archive_courses']
    
    def publish_courses(self, request, queryset):
        from django.utils import timezone
        updated = queryset.filter(status='under_review').update(
            status='published',
            published_at=timezone.now(),
            reviewed_by=request.user,
            reviewed_at=timezone.now()
        )
        self.message_user(request, f'{updated} course(s) published successfully.')
    publish_courses.short_description = 'Publish selected courses'
    
    def archive_courses(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status='archived',
            archived_at=timezone.now()
        )
        self.message_user(request, f'{updated} course(s) archived successfully.')
    archive_courses.short_description = 'Archive selected courses'


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'position', 'lesson_count', 'created_at')
    list_filter = ('course', 'created_at')
    search_fields = ('title', 'course__title')
    inlines = [LessonInline]
    
    def lesson_count(self, obj):
        return obj.lessons.count()
    lesson_count.short_description = 'Lessons'


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
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
    prepopulated_fields = {'slug': ('name',)}
    
    def course_count(self, obj):
        return obj.courses.count()
    course_count.short_description = 'Courses'


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'course_count')
    search_fields = ('name',)
    
    def course_count(self, obj):
        return obj.coursetag_set.count()
    course_count.short_description = 'Courses'


@admin.register(LessonResource)
class LessonResourceAdmin(admin.ModelAdmin):
    list_display = ('lesson', 'resource_type', 'uploaded_at')
    list_filter = ('resource_type', 'uploaded_at')
    search_fields = ('lesson__title',)
    readonly_fields = ('uploaded_at',)


@admin.register(CourseVersion)
class CourseVersionAdmin(admin.ModelAdmin):
    list_display = ('course', 'version_number', 'created_at')
    list_filter = ('course', 'created_at')
    search_fields = ('course__title',)
    readonly_fields = ('created_at',)


admin.site.register(CourseTag)
