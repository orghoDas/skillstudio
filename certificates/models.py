from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Certificate(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE)
    enrollment = models.OneToOneField(
        'enrollments.Enrollment',
        on_delete=models.CASCADE
    )

    certificate_id = models.CharField(max_length=64, unique=True)
    issued_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('user', 'course')

    def __str__(self):
        return f"Certificate — {self.user} — {self.course}"

