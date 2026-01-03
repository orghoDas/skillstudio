from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from .models import Enrollment, LessonProgress, Wishlist


# ===========================
# 🎓 Enrollment Admin
# ===========================

class LessonProgressInline(admin.TabularInline):
    """Inline display of lesson progress for an enrollment."""
    model = LessonProgress
    extra = 0
    readonly_fields = ['lesson', 'watch_time', 'is_completed', 'completed_at', 'started_at']
    can_delete = False
    
    fields = ['lesson', 'watch_time', 'is_completed', 'completed_at']
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Enrollment model."""
    
    list_display = [
        'id',
        'user_display',
        'course_display',
        'status_badge',
        'progress_bar',
        'enrolled_at',
        'completed_at',
    ]
    
    list_filter = [
        'status',
        'is_completed',
        'enrolled_at',
        'completed_at',
    ]
    
    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'course__title',
    ]
    
    readonly_fields = [
        'user',
        'course',
        'enrolled_at',
        'completed_at',
        'progress_display',
    ]
    
    fields = [
        'user',
        'course',
        'status',
        'is_completed',
        'enrolled_at',
        'completed_at',
        'progress_display',
    ]
    
    inlines = [LessonProgressInline]
    
    date_hierarchy = 'enrolled_at'
    
    list_per_page = 25
    
    actions = ['mark_as_completed', 'mark_as_active', 'mark_as_canceled']
    
    def user_display(self, obj):
        """Display user with link to admin."""
        return format_html(
            '<a href="/admin/accounts/user/{}/change/">{}</a>',
            obj.user.id,
            obj.user.get_full_name() or obj.user.email
        )
    user_display.short_description = 'Student'
    
    def course_display(self, obj):
        """Display course with link to admin."""
        return format_html(
            '<a href="/admin/courses/course/{}/change/">{}</a>',
            obj.course.id,
            obj.course.title
        )
    course_display.short_description = 'Course'
    
    def status_badge(self, obj):
        """Display status with colored badge."""
        colors = {
            'active': '#28a745',
            'completed': '#007bff',
            'canceled': '#dc3545',
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, '#6c757d'),
            obj.status.upper()
        )
    status_badge.short_description = 'Status'
    
    def progress_bar(self, obj):
        """Display progress as a visual bar."""
        from courses.models import Lesson
        
        total_lessons = Lesson.objects.filter(
            module__course=obj.course,
            is_free=False
        ).count()
        
        if total_lessons == 0:
            return format_html('<span>No lessons</span>')
        
        completed_lessons = obj.lesson_progress.filter(is_completed=True).count()
        progress = round((completed_lessons / total_lessons) * 100, 2)
        
        return format_html(
            '<div style="width:100px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width:{}%; background-color: #28a745; height: 20px; border-radius: 3px; text-align: center; color: white; font-size: 11px; line-height: 20px;">'
            '{}%'
            '</div>'
            '</div>',
            progress,
            progress
        )
    progress_bar.short_description = 'Progress'
    
    def progress_display(self, obj):
        """Display detailed progress information."""
        from courses.models import Lesson
        
        total_lessons = Lesson.objects.filter(
            module__course=obj.course,
            is_free=False
        ).count()
        
        completed_lessons = obj.lesson_progress.filter(is_completed=True).count()
        
        if total_lessons == 0:
            return 'No lessons in this course'
        
        progress = round((completed_lessons / total_lessons) * 100, 2)
        
        return format_html(
            '<strong>{}%</strong> ({} of {} lessons completed)',
            progress,
            completed_lessons,
            total_lessons
        )
    progress_display.short_description = 'Course Progress'
    
    # Admin Actions
    
    @admin.action(description='Mark selected enrollments as completed')
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(
            status='completed',
            is_completed=True,
            completed_at=timezone.now()
        )
        self.message_user(request, f'{updated} enrollment(s) marked as completed.')
    
    @admin.action(description='Mark selected enrollments as active')
    def mark_as_active(self, request, queryset):
        updated = queryset.update(status='active', is_completed=False, completed_at=None)
        self.message_user(request, f'{updated} enrollment(s) marked as active.')
    
    @admin.action(description='Mark selected enrollments as canceled')
    def mark_as_canceled(self, request, queryset):
        updated = queryset.update(status='canceled')
        self.message_user(request, f'{updated} enrollment(s) marked as canceled.')


# ===========================
# 📊 LessonProgress Admin
# ===========================

@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    """Enhanced admin interface for LessonProgress model."""
    
    list_display = [
        'id',
        'user_display',
        'lesson_display',
        'watch_time_display',
        'completion_badge',
        'started_at',
        'completed_at',
    ]
    
    list_filter = [
        'is_completed',
        'started_at',
        'completed_at',
    ]
    
    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'lesson__title',
        'enrollment__course__title',
    ]
    
    readonly_fields = [
        'user',
        'enrollment',
        'lesson',
        'started_at',
        'completed_at',
        'progress_percentage',
    ]
    
    fields = [
        'user',
        'enrollment',
        'lesson',
        'watch_time',
        'is_completed',
        'started_at',
        'completed_at',
        'progress_percentage',
    ]
    
    date_hierarchy = 'started_at'
    
    list_per_page = 25
    
    actions = ['mark_as_completed']
    
    def user_display(self, obj):
        """Display user with link."""
        return format_html(
            '<a href="/admin/accounts/user/{}/change/">{}</a>',
            obj.user.id,
            obj.user.get_full_name() or obj.user.email
        )
    user_display.short_description = 'Student'
    
    def lesson_display(self, obj):
        """Display lesson with course context."""
        return format_html(
            '{} <span style="color: #6c757d;">({})</span>',
            obj.lesson.title,
            obj.enrollment.course.title
        )
    lesson_display.short_description = 'Lesson'
    
    def watch_time_display(self, obj):
        """Display watch time as minutes and progress."""
        minutes = obj.watch_time // 60
        seconds = obj.watch_time % 60
        
        duration = obj.lesson.duration_seconds
        if duration > 0:
            progress = round((obj.watch_time / duration) * 100, 2)
            return format_html(
                '{}m {}s <span style="color: #6c757d;">({}%)</span>',
                minutes,
                seconds,
                progress
            )
        
        return f'{minutes}m {seconds}s'
    watch_time_display.short_description = 'Watch Time'
    
    def completion_badge(self, obj):
        """Display completion status with badge."""
        if obj.is_completed:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px;">✓ COMPLETED</span>'
            )
        return format_html(
            '<span style="background-color: #ffc107; color: black; padding: 3px 10px; border-radius: 3px;">IN PROGRESS</span>'
        )
    completion_badge.short_description = 'Status'
    
    def progress_percentage(self, obj):
        """Display progress as percentage."""
        duration = obj.lesson.duration_seconds
        if duration == 0:
            return 'N/A'
        
        progress = round((obj.watch_time / duration) * 100, 2)
        return f'{progress}%'
    progress_percentage.short_description = 'Progress'
    
    # Admin Actions
    
    @admin.action(description='Mark selected lessons as completed')
    def mark_as_completed(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(is_completed=True, completed_at=timezone.now())
        self.message_user(request, f'{updated} lesson(s) marked as completed.')


# ===========================
# 📋 Wishlist Admin
# ===========================

@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    """Enhanced admin interface for Wishlist model."""
    
    list_display = [
        'id',
        'user_display',
        'course_display',
        'course_price',
        'added_at',
    ]
    
    list_filter = [
        'added_at',
        'course__level',
        'course__category',
    ]
    
    search_fields = [
        'user__email',
        'user__first_name',
        'user__last_name',
        'course__title',
    ]
    
    readonly_fields = [
        'user',
        'course',
        'added_at',
    ]
    
    fields = [
        'user',
        'course',
        'added_at',
    ]
    
    date_hierarchy = 'added_at'
    
    list_per_page = 25
    
    def user_display(self, obj):
        """Display user with link."""
        return format_html(
            '<a href="/admin/accounts/user/{}/change/">{}</a>',
            obj.user.id,
            obj.user.get_full_name() or obj.user.email
        )
    user_display.short_description = 'User'
    
    def course_display(self, obj):
        """Display course with link."""
        return format_html(
            '<a href="/admin/courses/course/{}/change/">{}</a>',
            obj.course.id,
            obj.course.title
        )
    course_display.short_description = 'Course'
    
    def course_price(self, obj):
        """Display course price."""
        return format_html('${:.2f}', obj.course.price)
    course_price.short_description = 'Price'
