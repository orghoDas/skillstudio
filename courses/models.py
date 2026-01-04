from django.db import models
from django.utils import timezone
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return self.name


class Course(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('under_review', 'Under Review'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    ]

    LEVELS = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    instructor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='courses'
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name='courses'
    )

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.CharField(max_length=2000, blank=True)

    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_free = models.BooleanField(default=False)

    thumbnail = models.URLField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )

    level = models.CharField(
        max_length=20,
        choices=LEVELS,
        default='beginner'
    )

    current_version = models.ForeignKey(
        'CourseVersion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )

    # 🕒 Publishing lifecycle timestamps
    submitted_for_review_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    tags = models.ManyToManyField(
        Tag,
        through='CourseTag',
        blank=True
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_courses'
    )
    rejection_reason = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['instructor', 'status']),
            models.Index(fields=['status', 'published_at']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            
            # Keep appending numbers until we find a unique slug
            while True:
                if self.pk:
                    # Updating existing course - exclude self
                    exists = Course.objects.filter(slug=slug).exclude(pk=self.pk).exists()
                else:
                    # Creating new course
                    exists = Course.objects.filter(slug=slug).exists()
                
                if not exists:
                    break
                    
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            self.slug = slug
        super().save(*args, **kwargs)

    def clean(self):
        if self.is_free:
            self.price = 0

    # 🧠 Helper methods (used later in views & permissions)
    def is_editable(self):
        return self.status in ['draft', 'under_review']

    def is_public(self):
        return self.status == 'published'



class CourseVersion(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='versions')
    version_number = models.IntegerField()
    data = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('course', 'version_number')
        ordering = ['-version_number']

    def __str__(self):
        return f"{self.course.title} - v{self.version_number}"


class CourseTag(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('course', 'tag')


class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"{self.course.title} - {self.title}"
    

class Lesson(models.Model):
    CONTENT_CHOICES = [
        ('video', 'Video'),
        ('text', 'Text'),
        ('quiz', 'Quiz'),
        ('assignment', 'Assignment'),
        ('resource', 'Resource'),
    ]

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=255)
    content_type = models.CharField(max_length=20, choices=CONTENT_CHOICES, default='video')
    content_text = models.TextField(blank=True)
    video_url = models.URLField(blank=True)
    duration_seconds = models.PositiveIntegerField(default=0, help_text="Duration in seconds")
    metadata = models.JSONField(default=dict, blank=True, null=True)
    position = models.PositiveIntegerField(default=0)
    is_free = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return self.title
    
    def clean(self):
        # Optional validation - allow draft lessons without full content
        # Only validate if explicitly requested
        pass
        
    def save(self, *args, **kwargs):
        # Skip full_clean to allow creating draft lessons
        # Validation can be done when publishing the course
        super().save(*args, **kwargs)


class LessonResource(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources')
    file_url = models.TextField()
    resource_type = models.CharField(max_length=50, blank=True, null=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.lesson.title} - {self.resource_type}"
