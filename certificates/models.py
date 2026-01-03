import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL


class Certificate(models.Model):
    """Certificate issued to users upon course completion."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates"
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="certificates"
    )
    enrollment = models.OneToOneField(
        "enrollments.Enrollment",
        on_delete=models.CASCADE,
        related_name="certificate",
        null=True,
        blank=True
    )

    certificate_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True
    )

    verification_code = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False
    )

    pdf = models.FileField(
        upload_to="certificates/%Y/%m/",
        null=True,
        blank=True
    )
    
    # Metadata
    grade = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Final course grade percentage"
    )
    completion_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when course was completed"
    )
    issued_at = models.DateTimeField(default=timezone.now)
    
    # Tracking
    download_count = models.IntegerField(default=0)
    last_downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "course"],
                name="unique_certificate_per_user_course"
            )
        ]
        ordering = ['-issued_at']
        indexes = [
            models.Index(fields=['user', 'course']),
            models.Index(fields=['verification_code']),
        ]

    def __str__(self):
        return f"{self.user} - {self.course}"
    
    def save(self, *args, **kwargs):
        if not self.verification_code:
            self.verification_code = str(uuid.uuid4())
        super().save(*args, **kwargs)
    
    @property
    def verification_url(self):
        """Get the full verification URL."""
        from django.conf import settings
        return f"{settings.BACKEND_URL}/api/certificates/verify/{self.verification_code}/"
    
    def increment_download_count(self):
        """Increment download counter."""
        self.download_count += 1
        self.last_downloaded_at = timezone.now()
        self.save(update_fields=['download_count', 'last_downloaded_at'])

