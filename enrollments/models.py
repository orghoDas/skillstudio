from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

User = settings.AUTH_USER_MODEL


# PostgreSQL Equivalent:
# CREATE TABLE enrollments_enrollment (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'canceled')),
#     enrolled_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     completed_at TIMESTAMP WITH TIME ZONE,
#     progress JSONB DEFAULT '{}',
#     completed BOOLEAN NOT NULL DEFAULT FALSE,
#     UNIQUE (user_id, course_id)
# );
# CREATE INDEX enrollments_enrollment_user_course_idx ON enrollments_enrollment(user_id, course_id);
class Enrollment(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='enrollments')
    status  = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    enrolled_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    progress = models.JSONField(default=dict, blank=True)
    completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'course')   
        indexes = [models.Index(fields=['user', 'course'])]

    def __str__(self):
        return f"{self.user} enrolled in {self.course} - {self.status}"


# PostgreSQL Equivalent:
# CREATE TABLE enrollments_lessonprogress (
#     id SERIAL PRIMARY KEY,
#     enrollment_id INTEGER REFERENCES enrollments_enrollment(id) ON DELETE CASCADE,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     lesson_id INTEGER NOT NULL REFERENCES courses_lesson(id) ON DELETE CASCADE,
#     is_completed BOOLEAN NOT NULL DEFAULT FALSE,
#     watch_time INTEGER NOT NULL DEFAULT 0 CHECK (watch_time >= 0),
#     started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     completed_at TIMESTAMP WITH TIME ZONE,
#     UNIQUE (enrollment_id, lesson_id)
# );
# CREATE INDEX enrollments_lessonprogress_lesson_completed_idx ON enrollments_lessonprogress(lesson_id, is_completed);
class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='lesson_progress')
    is_completed = models.BooleanField(default=False)
    watch_time = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')
        indexes = [models.Index(fields=['lesson', 'is_completed'])]

    def __str__(self):
        return f'{self.enrollment.user} - {self.lesson.title}'


# PostgreSQL Equivalent:
# CREATE TABLE enrollments_wishlist (
#     id SERIAL PRIMARY KEY,
#     user_id INTEGER NOT NULL REFERENCES accounts_user(id) ON DELETE CASCADE,
#     course_id INTEGER NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
#     UNIQUE (user_id, course_id)
# );
# CREATE INDEX enrollments_wishlist_user_id_idx ON enrollments_wishlist(user_id);
# CREATE INDEX enrollments_wishlist_course_id_idx ON enrollments_wishlist(course_id);
class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlists')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='wishlists')
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'course')

