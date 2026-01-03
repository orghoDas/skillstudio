from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class StudentProfile(models.Model):
    """Extended profile information for students."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    
    # Learning preferences
    preferred_learning_style = models.CharField(
        max_length=20,
        choices=[
            ('visual', 'Visual'),
            ('auditory', 'Auditory'),
            ('reading', 'Reading/Writing'),
            ('kinesthetic', 'Kinesthetic'),
        ],
        blank=True,
        null=True
    )
    
    # Goals and interests
    learning_goals = models.TextField(blank=True, help_text="Student's learning objectives")
    interests = models.JSONField(default=list, help_text="List of interest tags")
    
    # Time availability
    weekly_study_hours = models.IntegerField(
        default=0,
        help_text="Target study hours per week"
    )
    preferred_study_time = models.CharField(
        max_length=20,
        choices=[
            ('morning', 'Morning'),
            ('afternoon', 'Afternoon'),
            ('evening', 'Evening'),
            ('night', 'Night'),
        ],
        blank=True,
        null=True
    )
    
    # Statistics (denormalized for performance)
    total_courses_enrolled = models.IntegerField(default=0)
    total_courses_completed = models.IntegerField(default=0)
    total_certificates_earned = models.IntegerField(default=0)
    total_watch_time = models.IntegerField(default=0, help_text="Total watch time in seconds")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"Student Profile: {self.user.email}"
    
    def update_statistics(self):
        """Update denormalized statistics from related models."""
        from enrollments.models import Enrollment
        from certificates.models import Certificate
        from enrollments.models import LessonProgress
        
        self.total_courses_enrolled = Enrollment.objects.filter(user=self.user).count()
        self.total_courses_completed = Enrollment.objects.filter(
            user=self.user, is_completed=True
        ).count()
        self.total_certificates_earned = Certificate.objects.filter(user=self.user).count()
        self.total_watch_time = LessonProgress.objects.filter(user=self.user).aggregate(
            total=models.Sum('watch_time')
        )['total'] or 0
        
        self.save(update_fields=[
            'total_courses_enrolled',
            'total_courses_completed',
            'total_certificates_earned',
            'total_watch_time',
        ])


class StudentNote(models.Model):
    """Notes taken by students during lessons."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='student_notes')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='student_notes')
    
    # Note content
    content = models.TextField()
    timestamp = models.IntegerField(
        default=0,
        help_text="Video timestamp in seconds where note was taken"
    )
    
    # Organization
    is_pinned = models.BooleanField(default=False)
    tags = models.JSONField(default=list)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_notes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'lesson']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['is_pinned', '-created_at']),
        ]
    
    def __str__(self):
        return f"Note by {self.user.email} on {self.lesson.title}"


class StudentBookmark(models.Model):
    """Bookmarked lessons or courses for later review."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    
    # Bookmarked content
    course = models.ForeignKey(
        'courses.Course',
        on_delete=models.CASCADE,
        related_name='bookmarks',
        null=True,
        blank=True
    )
    lesson = models.ForeignKey(
        'courses.Lesson',
        on_delete=models.CASCADE,
        related_name='bookmarks',
        null=True,
        blank=True
    )
    
    # Notes
    note = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'student_bookmarks'
        ordering = ['-created_at']
        unique_together = [
            ['user', 'course'],
            ['user', 'lesson'],
        ]
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]
    
    def __str__(self):
        if self.lesson:
            return f"Bookmark: {self.user.email} -> {self.lesson.title}"
        return f"Bookmark: {self.user.email} -> {self.course.title}"
