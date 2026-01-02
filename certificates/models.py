import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Certificate(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="certificates"
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="certificates"
    )

    certificate_code = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False
    )

    issued_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("user", "course")
        indexes = [
            models.Index(fields=["certificate_code"]),
            models.Index(fields=["user", "course"])
        ]

    def __str__(self):
        return f"{self.user} - {self.course}"
