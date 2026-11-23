import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from django.utils.functional import cached_property

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
    pdf_verification_url = models.CharField(max_length=500, blank=True)
    pdf_learner_name = models.CharField(max_length=255, blank=True, default='', db_default='')
    pdf_grade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    
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
    revoked_at = models.DateTimeField(null=True, blank=True)
    
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
    def verification_url(self) -> str:
        path = reverse('certificate-verification-page', kwargs={'code': self.verification_code})
        return f"{settings.BACKEND_URL}{path}"

    @property
    def is_revoked(self):
        return self.revoked_at is not None or (self.enrollment is not None and self.enrollment.status == 'canceled')

    @staticmethod
    def unreleased_exam_attempts(user_id, course_id, issued_at):
        from exams.models import ExamAttempt

        return ExamAttempt.objects.filter(
            user_id=user_id, exam__course_id=course_id,
            exam__show_results_immediately=False,
            status='completed', score__isnull=False,
        ).filter(
            models.Q(completed_at__isnull=True) | models.Q(completed_at__lte=issued_at),
        )

    @cached_property
    def released_grade(self):
        if self.grade is None:
            return None
        unreleased = getattr(self, 'has_unreleased_exam_grades', None)
        if unreleased is None:
            unreleased = self.unreleased_exam_attempts(self.user_id, self.course_id, self.issued_at).exists()
        return None if unreleased else self.grade
    
    def increment_download_count(self):
        """Increment download counter."""
        type(self).objects.filter(pk=self.pk).update(
            download_count=models.F('download_count') + 1,
            last_downloaded_at=timezone.now(),
        )
        self.refresh_from_db(fields=['download_count', 'last_downloaded_at'])
