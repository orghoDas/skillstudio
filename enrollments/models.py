from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


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

    is_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'course')   
        indexes = [models.Index(fields=['user', 'course']),
                   models.Index(fields=['course', 'status'])]

    def __str__(self):
        return f"{self.user.email} - {self.course.title}"

# PostgreSQL equivalent for enrollments:
# CREATE TABLE IF NOT EXISTS enrollments_enrollment (
#     id serial PRIMARY KEY,
#     user_id integer NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
#     course_id integer NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     status varchar(20) NOT NULL DEFAULT 'active',
#     enrolled_at timestamptz NOT NULL DEFAULT now(),
#     completed_at timestamptz NULL,
#     is_completed boolean NOT NULL DEFAULT false,
#     UNIQUE (user_id, course_id)
# );
# CREATE INDEX IF NOT EXISTS idx_enrollments_enrollment_user_course ON enrollments_enrollment (user_id, course_id);
# CREATE INDEX IF NOT EXISTS idx_enrollments_enrollment_course_status ON enrollments_enrollment (course_id, status);


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progress')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='lesson_progress')
    lesson = models.ForeignKey('courses.Lesson', on_delete=models.CASCADE, related_name='lesson_progress')
    is_completed = models.BooleanField(default=False)
    watch_time = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True,  blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')
        indexes = [models.Index(fields=['lesson', 'is_completed']),
                   models.Index(fields=['enrollment'])]

    def __str__(self):
        return f'{self.user} - {self.lesson.title}'

# PostgreSQL equivalent for lesson progress:
# CREATE TABLE IF NOT EXISTS enrollments_lessonprogress (
#     id serial PRIMARY KEY,
#     enrollment_id integer NOT NULL REFERENCES enrollments_enrollment(id) ON DELETE CASCADE,
#     user_id integer NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
#     lesson_id integer NOT NULL REFERENCES courses_lesson(id) ON DELETE CASCADE,
#     is_completed boolean NOT NULL DEFAULT false,
#     watch_time integer NOT NULL DEFAULT 0,
#     started_at timestamptz NOT NULL DEFAULT now(),
#     completed_at timestamptz NULL,
#     updated_at timestamptz NOT NULL DEFAULT now(),
#     UNIQUE (enrollment_id, lesson_id)
# );
# CREATE INDEX IF NOT EXISTS idx_enrollments_lessonprogress_lesson_completed ON enrollments_lessonprogress (lesson_id, is_completed);
# CREATE INDEX IF NOT EXISTS idx_enrollments_lessonprogress_enrollment ON enrollments_lessonprogress (enrollment_id);


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlists')
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='wishlists')
    added_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'course')

# PostgreSQL equivalent for wishlist:
# CREATE TABLE IF NOT EXISTS enrollments_wishlist (
#     id serial PRIMARY KEY,
#     user_id integer NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
#     course_id integer NOT NULL REFERENCES courses_course(id) ON DELETE CASCADE,
#     added_at timestamptz NOT NULL DEFAULT now(),
#     UNIQUE (user_id, course_id)
# );

