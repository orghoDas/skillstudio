from itertools import count
from decimal import Decimal

from django.db import IntegrityError, models, router, transaction
from django.utils import timezone
from django.conf import settings
from django.utils.text import slugify
from django.core.validators import MinValueValidator

User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *, force_insert=False, force_update=False, using=None, update_fields=None):
        options = {
            'force_insert': force_insert, 'force_update': force_update,
            'using': using, 'update_fields': update_fields,
        }
        if self.slug or (update_fields is not None and not update_fields):
            return super().save(**options)

        using = using or router.db_for_write(type(self), instance=self)
        options['using'] = using
        if update_fields is not None:
            options['update_fields'] = set(update_fields) | {'slug'}
        other = type(self).objects.using(using).exclude(pk=self.pk)
        base = slugify(self.name) or 'category'
        max_length = self._meta.get_field('slug').max_length
        for number in count():
            suffix = f'-{number}' if number else ''
            candidate = f'{base[:max_length - len(suffix)]}{suffix}'
            if other.filter(slug=candidate).exists():
                continue
            self.slug = candidate
            try:
                with transaction.atomic(using=using):
                    return super().save(**options)
            except IntegrityError:
                self.slug = ''
                # A concurrent insert can claim the slug between the check
                # and the write. A duplicate name cannot be fixed by retrying.
                if other.filter(name=self.name).exists() or not other.filter(slug=candidate).exists():
                    raise


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return self.name


# Single-segment paths under /api/courses/ that a course slug must never equal,
# or the slug route would be shadowed / shadow the fixed route (API-02).
RESERVED_COURSE_SLUGS = frozenset({
    'admin', 'categories', 'create', 'instructor', 'lessons', 'modules', 'sections', 'tags',
})


def safe_course_slug_base(title):
    """slugify(title), but never empty, purely numeric (``<int:id>/`` would win)
    or a reserved route word."""
    base = slugify(title or '') or 'course'
    if base.isdigit() or base in RESERVED_COURSE_SLUGS:
        base = f'{base}-course'
    return base


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

    price = models.DecimalField(
        max_digits=8, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))],
    )
    # When omitted on a new model instance, infer the flag from the price.
    is_free = models.BooleanField(default=None)

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
    revision_of = models.OneToOneField(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='successor', editable=False,
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
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_free=True, price=0) | models.Q(is_free=False, price__gt=0),
                name='course_price_matches_free_flag',
            ),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = safe_course_slug_base(self.title)[:255]
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
                    
                suffix = f"-{counter}"
                slug = f"{base_slug[:255 - len(suffix)]}{suffix}"
                counter += 1
            
            self.slug = slug
        if self._state.adding and self.is_free is None:
            self.is_free = self._meta.get_field('price').to_python(self.price) == 0
        if self.is_free:
            self.price = 0
            update_fields = kwargs.get('update_fields')
            if update_fields is not None and 'is_free' in update_fields:
                kwargs['update_fields'] = set(update_fields) | {'price'}
        super().save(*args, **kwargs)

    # 🧠 Helper methods (used later in views & permissions)
    def is_editable(self):
        return self.status == 'draft'

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
        ordering = ['position', 'id']

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    

class Lesson(models.Model):
    CONTENT_CHOICES = [
        ('video', 'Video'),
        ('text', 'Text'),
        ('quiz', 'Quiz'),
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
        ordering = ['position', 'id']
        constraints = [
            models.UniqueConstraint(fields=['module', 'position'], name='unique_lesson_position_per_module'),
        ]

    def __str__(self):
        return self.title
    

class LessonResource(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources')
    file_url = models.TextField()
    resource_type = models.CharField(max_length=50, blank=True, null=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.lesson.title} - {self.resource_type}"
