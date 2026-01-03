from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class CourseAnalyticsSnapshot(models.Model):
    """Daily snapshot of course analytics for historical tracking"""
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="analytics_snapshots")
    snapshot_date = models.DateField(auto_now_add=True)
    total_enrollments = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    total_watch_minutes = models.PositiveIntegerField(default=0)
    unique_viewers = models.PositiveIntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("course", "snapshot_date")
        ordering = ['-snapshot_date']
        indexes = [
            models.Index(fields=['course', '-snapshot_date']),
        ]

    def __str__(self):
        return f"{self.course.title} - {self.snapshot_date}"


class UserInteraction(models.Model):
    """Track user interactions across the platform"""
    ACTION_TYPES = [
        ('view_course', 'View Course'),
        ('enroll_course', 'Enroll in Course'),
        ('complete_lesson', 'Complete Lesson'),
        ('start_lesson', 'Start Lesson'),
        ('submit_quiz', 'Submit Quiz'),
        ('post_review', 'Post Review'),
        ('bookmark_course', 'Bookmark Course'),
        ('search', 'Search'),
        ('view_event', 'View Event'),
        ('register_event', 'Register for Event'),
        ('join_circle', 'Join Learning Circle'),
        ('create_post', 'Create Forum Post'),
        ('like_post', 'Like Post'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='interactions')
    course = models.ForeignKey("courses.Course", on_delete=models.SET_NULL, null=True, blank=True, related_name='interactions')
    event = models.ForeignKey("events.Event", on_delete=models.SET_NULL, null=True, blank=True, related_name='interactions')
    action = models.CharField(max_length=100, choices=ACTION_TYPES)
    metadata = models.JSONField(default=dict, blank=True)
    session_id = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['course', '-created_at']),
        ]

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.created_at}"


class InstructorAnalytics(models.Model):
    """Aggregated analytics for instructors"""
    instructor = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='instructor_analytics',
        limit_choices_to={'role': 'instructor'}
    )
    total_courses = models.PositiveIntegerField(default=0)
    total_students = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    total_reviews = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Instructor Analytics'

    def __str__(self):
        return f"{self.instructor.email} - Analytics"


class LessonAnalytics(models.Model):
    """Analytics for individual lessons"""
    lesson = models.OneToOneField(
        "courses.Lesson",
        on_delete=models.CASCADE,
        related_name='analytics'
    )
    total_views = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    average_watch_time = models.PositiveIntegerField(default=0)  # in seconds
    drop_off_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)  # percentage
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Lesson Analytics'

    def __str__(self):
        return f"{self.lesson.title} - Analytics"


class EventAnalytics(models.Model):
    """Analytics for events"""
    event = models.OneToOneField(
        "events.Event",
        on_delete=models.CASCADE,
        related_name='analytics'
    )
    total_registrations = models.PositiveIntegerField(default=0)
    total_attendees = models.PositiveIntegerField(default=0)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Event Analytics'

    def __str__(self):
        return f"{self.event.title} - Analytics"


class SearchQuery(models.Model):
    """Track search queries for analytics and recommendations"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_queries'
    )
    query = models.CharField(max_length=500)
    results_count = models.PositiveIntegerField(default=0)
    clicked_result = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_clicks'
    )
    filters = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['query']),
        ]

    def __str__(self):
        return f"{self.query} - {self.results_count} results"


class DailyPlatformMetrics(models.Model):
    """Daily aggregated platform-wide metrics"""
    date = models.DateField(unique=True)
    total_users = models.PositiveIntegerField(default=0)
    new_users = models.PositiveIntegerField(default=0)
    active_users = models.PositiveIntegerField(default=0)
    total_enrollments = models.PositiveIntegerField(default=0)
    new_enrollments = models.PositiveIntegerField(default=0)
    total_completions = models.PositiveIntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_courses = models.PositiveIntegerField(default=0)
    total_events = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['-date']),
        ]

    def __str__(self):
        return f"Metrics for {self.date}"

