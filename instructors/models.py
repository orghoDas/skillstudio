from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()


class InstructorProfile(models.Model):
    """Extended profile information for instructors."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='instructor_profile')
    
    # Professional information
    bio = models.TextField(blank=True, help_text="Instructor biography")
    headline = models.CharField(max_length=255, blank=True, help_text="Professional headline")
    website = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    
    # Expertise
    expertise_areas = models.JSONField(default=list, help_text="List of expertise areas")
    years_of_experience = models.IntegerField(default=0)
    
    # Credentials
    certifications = models.JSONField(default=list, help_text="List of certifications")
    education = models.JSONField(default=list, help_text="Educational background")
    
    # Verification
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'instructor_profiles'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['is_verified']),
        ]
    
    def __str__(self):
        return f"Instructor Profile: {self.user.email}"
    
    def verify(self):
        """Mark instructor as verified."""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=['is_verified', 'verified_at'])
    
    @property
    def total_courses(self) -> int:
        from courses.models import Course

        return Course.objects.filter(instructor_id=self.user_id).count()

    @property
    def total_students(self) -> int:
        from enrollments.models import Enrollment

        return Enrollment.objects.filter(course__instructor_id=self.user_id).values('user').distinct().count()

    @property
    def total_revenue(self):
        from payments.services import get_instructor_net_earnings

        return get_instructor_net_earnings(self.user_id)


# InstructorPayout was removed (AUDIT_REPORT.md PAY-07, 2026-11-21): payouts
# live only in payments.Payout and are paid from the instructor's wallet.
