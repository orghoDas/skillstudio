from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
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
    
    # Statistics (denormalized for performance)
    total_courses = models.IntegerField(default=0)
    total_students = models.IntegerField(default=0)
    total_revenue = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
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
            models.Index(fields=['-total_students']),
        ]
    
    def __str__(self):
        return f"Instructor Profile: {self.user.email}"
    
    def verify(self):
        """Mark instructor as verified."""
        self.is_verified = True
        self.verified_at = timezone.now()
        self.save(update_fields=['is_verified', 'verified_at'])
    
    def update_statistics(self):
        """Update denormalized statistics from related models."""
        from courses.models import Course
        from enrollments.models import Enrollment
        from payments.models import Payment
        
        courses = Course.objects.filter(instructor=self.user)
        self.total_courses = courses.count()
        
        self.total_students = Enrollment.objects.filter(
            course__instructor=self.user
        ).values('user').distinct().count()
        
        self.total_revenue = Payment.objects.filter(
            instructor=self.user,
            status='completed'
        ).aggregate(
            total=models.Sum('instructor_earnings')
        )['total'] or Decimal('0.00')
        
        self.save(update_fields=[
            'total_courses',
            'total_students',
            'total_revenue',
        ])


# InstructorPayout was removed (AUDIT_REPORT.md PAY-07, 2026-11-21): payouts
# live only in payments.Payout and are paid from the instructor's wallet.
