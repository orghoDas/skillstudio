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
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('0.00'))
    total_reviews = models.IntegerField(default=0)
    
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
            models.Index(fields=['-average_rating']),
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
        from social.models import Review
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
        
        reviews = Review.objects.filter(course__instructor=self.user)
        self.total_reviews = reviews.count()
        
        if self.total_reviews > 0:
            self.average_rating = reviews.aggregate(
                avg=models.Avg('rating')
            )['avg'] or Decimal('0.00')
        else:
            self.average_rating = Decimal('0.00')
        
        self.save(update_fields=[
            'total_courses',
            'total_students',
            'total_revenue',
            'average_rating',
            'total_reviews',
        ])


class InstructorPayout(models.Model):
    """Track instructor payout requests and history."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payout_requests')
    
    # Amount
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Payment method
    payment_method = models.CharField(max_length=50, default='bank_transfer')
    payment_details = models.JSONField(default=dict, help_text="Payment method details")
    
    # Transaction info
    transaction_id = models.CharField(max_length=255, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'instructor_payouts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['instructor', '-created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Payout {self.id}: {self.instructor.email} - ${self.amount}"
    
    def complete(self, transaction_id):
        """Mark payout as completed."""
        self.status = 'completed'
        self.transaction_id = transaction_id
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'transaction_id', 'processed_at'])
    
    def fail(self, notes=''):
        """Mark payout as failed."""
        self.status = 'failed'
        self.notes = notes
        self.save(update_fields=['status', 'notes'])
