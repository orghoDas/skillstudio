from django.db import models
from django.utils import timezone
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
# Create your models here.

User = settings.AUTH_USER_MODEL


# PostgreSQL Equivalent:
# CREATE TABLE courses_category (
#     id SERIAL PRIMARY KEY,
#     name VARCHAR(100) UNIQUE NOT NULL,
#     slug VARCHAR(100) UNIQUE NOT NULL
# );
# CREATE INDEX courses_category_slug_idx ON courses_category(slug);
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)

    def __str__(self):
        return self.name
    

# PostgreSQL Equivalent:
# CREATE TABLE courses_tag (
#     id SERIAL PRIMARY KEY,
#     name VARCHAR(50) UNIQUE NOT NULL
# );
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
    def __str__(self):
        return self.name
    

# PostgreSQL Equivalent:
# CREATE TABLE courses_course (
#     id SERIAL PRIMARY KEY,
#     instructor_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     category_id INTEGER REFERENCES courses_category(id) ON DELETE SET NULL,
#     title VARCHAR(255) NOT NULL,
#     slug VARCHAR(255) UNIQUE NOT NULL,
#     description VARCHAR(2000) DEFAULT '',
#     price DECIMAL(8, 2) NOT NULL DEFAULT 0,
#     is_free BOOLEAN NOT NULL DEFAULT FALSE,
#     thumbnail VARCHAR(200),
#     status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived', 'under_review')),
#     level VARCHAR(20) NOT NULL DEFAULT 'beginner' CHECK (level IN ('beginner', 'intermediate', 'advanced')),
#     current_version_id INTEGER REFERENCES courses_courseversion(id) ON DELETE SET NULL,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX courses_course_instructor_status_idx ON courses_course(instructor_id, status);
# CREATE INDEX courses_course_slug_idx ON courses_course(slug);
class Course(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('archived', 'Archived'),
        ('under_review', 'Under Review'),
    ]

    LEVELS = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
    ]

    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='courses')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='courses')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.CharField(max_length=2000, blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_free = models.BooleanField(default=False)
    thumbnail = models.URLField(blank=True, null = True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    level = models.CharField(max_length=20, choices=LEVELS, default='beginner')
    current_version = models.ForeignKey('CourseVersion', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    tags = models.ManyToManyField(Tag, through='CourseTag', blank=True)

    class Meta:
        indexes = [models.Index(fields=['instructor', 'status'])]

    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def clean(self):
        if self.is_free:
            self.price = 0
    

# PostgreSQL Equivalent:
# CREATE TABLE courses_courseversion (
#     id SERIAL PRIMARY KEY,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     version_number INTEGER NOT NULL CHECK (version_number >= 0),
#     title VARCHAR(255) NOT NULL DEFAULT 'Version',
#     content JSONB NOT NULL DEFAULT '{}',
#     published BOOLEAN NOT NULL DEFAULT FALSE,
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     UNIQUE (course_id, version_number)
# );
# CREATE INDEX courses_courseversion_course_id_idx ON courses_courseversion(course_id);
class CourseVersion(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255, default='Version')
    content = models.JSONField(default=dict)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('course', 'version_number')
        ordering = ['-version_number']


# PostgreSQL Equivalent:
# CREATE TABLE courses_coursetag (
#     id SERIAL PRIMARY KEY,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     tag_id INTEGER NOT NULL REFERENCES courses_tag(id) ON DELETE CASCADE,
#     UNIQUE (course_id, tag_id)
# );
# CREATE INDEX courses_coursetag_course_id_idx ON courses_coursetag(course_id);
# CREATE INDEX courses_coursetag_tag_id_idx ON courses_coursetag(tag_id);
class CourseTag(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('course', 'tag')


# PostgreSQL Equivalent:
# CREATE TABLE courses_module (
#     id SERIAL PRIMARY KEY,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     title VARCHAR(255) NOT NULL,
#     position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX courses_module_course_id_idx ON courses_module(course_id);
# CREATE INDEX courses_module_position_idx ON courses_module(position);
class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=255)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return f"{self.course.title} - {self.title}"
    

# PostgreSQL Equivalent:
# CREATE TABLE courses_lesson (
#     id SERIAL PRIMARY KEY,
#     module_id INTEGER NOT NULL REFERENCES courses_module(id) ON DELETE CASCADE,
#     title VARCHAR(255) NOT NULL,
#     content_type VARCHAR(20) NOT NULL DEFAULT 'video' CHECK (content_type IN ('video', 'text', 'quiz', 'assignment', 'resource')),
#     content_text TEXT DEFAULT '',
#     video_url VARCHAR(200) DEFAULT '',
#     metadata JSONB DEFAULT '{}',
#     position INTEGER NOT NULL DEFAULT 0 CHECK (position >= 0),
#     created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     view_count INTEGER NOT NULL DEFAULT 0 CHECK (view_count >= 0)
# );
# CREATE INDEX courses_lesson_module_id_idx ON courses_lesson(module_id);
# CREATE INDEX courses_lesson_position_idx ON courses_lesson(position);
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
    metadata = models.JSONField(default=dict, blank=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position']

    def __str__(self):
        return self.title
    
    def clean(self):
        if self.content_type == 'video' and not self.video_url:
            raise ValidationError("Video lessons must have a video URL.")

        if self.content_type == 'text' and not self.content_text:
            raise ValidationError("Text lessons must have content.")

        if self.content_type == 'quiz' and self.content_text:
            raise ValidationError("Quiz lessons should not store text content.")
        if self.content_type == 'resource' and not self.resources.exists():
            raise ValidationError("Resource lessons must have at least one resource.")
        
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    

# PostgreSQL Equivalent:
# CREATE TABLE courses_lessonresource (
#     id SERIAL PRIMARY KEY,
#     lesson_id INTEGER NOT NULL REFERENCES courses_lesson(id) ON DELETE CASCADE,
#     file_url TEXT NOT NULL,
#     recourse_type VARCHAR(50),
#     uploaded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
# );
# CREATE INDEX courses_lessonresource_lesson_id_idx ON courses_lessonresource(lesson_id);
class LessonResource(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='resources')
    file_url = models.TextField()
    recourse_type = models.CharField(max_length=50, blank=True, null=True)
    uploaded_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.lesson.title} - {self.resource_type}"
