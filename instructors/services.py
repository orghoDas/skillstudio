from django.db import models, transaction
from django.db.models import Count, Avg, Max, Sum, Q
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal

from courses.models import Course
from enrollments.models import Enrollment, LessonProgress
from payments.models import Payment, Payout
# from events.models import Event  # Removed - events app disabled
from .models import InstructorProfile, InstructorPayout


def get_course_overview(instructor):
    """Get course overview with enrollment and rating statistics."""
    return (
        Course.objects
        .filter(instructor=instructor)
        .annotate(
            total_enrollments=Count("enrollments"),
            avg_rating=Avg("reviews__rating"),
        )
    )


def get_student_engagement(instructor):
    """Get student engagement metrics for instructor's courses."""
    return (
        Enrollment.objects
        .filter(course__instructor=instructor)
        .annotate(
            completed_lessons=Count(
                "lesson_progress",
                filter=Q(lesson_progress__is_completed=True)
            ),
            last_activity=Max("lesson_progress__updated_at")
        )
        .select_related("course", "user")
    )


def get_lesson_dropoff(course):
    """Get lesson dropout statistics for a course."""
    return (
        LessonProgress.objects
        .filter(lesson__module__course=course)
        .values("lesson__id", "lesson__title")
        .annotate(students=Count("user"))
        .order_by("students")
    )


def get_revenue_summary(instructor):
    """Get revenue summary and payout history for instructor."""
    earnings = (
        Payment.objects
        .filter(instructor=instructor, status="completed")
        .aggregate(
            total_earned=Sum("instructor_earnings"),
            platform_fee=Sum("platform_fee"),
        )
    )

    payouts = (
        Payout.objects
        .filter(instructor=instructor)
        .order_by("-created_at")
    )

    return earnings, payouts


# Removed - events app disabled
# def get_instructor_events(instructor):
#     """Get events hosted by instructor."""
#     return Event.objects.filter(host=instructor)


@transaction.atomic
def get_or_create_instructor_profile(user):
    """
    Get or create instructor profile for a user.
    
    Args:
        user: User instance
    
    Returns:
        InstructorProfile instance
    """
    profile, created = InstructorProfile.objects.get_or_create(
        user=user,
        defaults={
            'is_verified': False,
        }
    )
    
    if created:
        # Initialize statistics
        profile.update_statistics()
    
    return profile


@transaction.atomic
def update_instructor_profile(user, **kwargs):
    """
    Update instructor profile.
    
    Args:
        user: User instance
        **kwargs: Fields to update
    
    Returns:
        Updated InstructorProfile instance
    
    Raises:
        ValidationError: If user doesn't have a profile
    """
    try:
        profile = InstructorProfile.objects.get(user=user)
    except InstructorProfile.DoesNotExist:
        raise ValidationError("Instructor profile not found.")
    
    # Only allow updating certain fields
    allowed_fields = [
        'bio',
        'headline',
        'website',
        'linkedin',
        'twitter',
        'expertise_areas',
        'years_of_experience',
        'certifications',
        'education',
    ]
    
    for field, value in kwargs.items():
        if field in allowed_fields:
            setattr(profile, field, value)
    
    profile.save()
    return profile


@transaction.atomic
def request_payout(instructor, amount, payment_method='bank_transfer', payment_details=None):
    """
    Request a payout for an instructor.
    
    Args:
        instructor: User instance
        amount: Payout amount
        payment_method: Payment method
        payment_details: Payment method details dict
    
    Returns:
        InstructorPayout instance
    
    Raises:
        ValidationError: If amount invalid or insufficient balance
    """
    if amount <= 0:
        raise ValidationError("Payout amount must be greater than zero.")
    
    # Check available balance
    earnings = Payment.objects.filter(
        instructor=instructor,
        status='completed'
    ).aggregate(
        total=Sum('instructor_earnings')
    )['total'] or Decimal('0.00')
    
    paid_out = InstructorPayout.objects.filter(
        instructor=instructor,
        status__in=['completed', 'processing']
    ).aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0.00')
    
    available = earnings - paid_out
    
    if amount > available:
        raise ValidationError(f"Insufficient balance. Available: ${available}")
    
    payout = InstructorPayout.objects.create(
        instructor=instructor,
        amount=amount,
        payment_method=payment_method,
        payment_details=payment_details or {}
    )
    
    return payout


@transaction.atomic
def complete_payout(payout_id, transaction_id, admin_user):
    """
    Complete a payout (admin only).
    
    Args:
        payout_id: Payout UUID
        transaction_id: Transaction ID from payment processor
        admin_user: Admin user completing the payout
    
    Returns:
        Updated InstructorPayout instance
    
    Raises:
        ValidationError: If payout not found
        PermissionDenied: If user is not staff
    """
    if not admin_user.is_staff:
        raise PermissionDenied("Only staff can complete payouts.")
    
    try:
        payout = InstructorPayout.objects.get(id=payout_id)
    except InstructorPayout.DoesNotExist:
        raise ValidationError("Payout not found.")
    
    payout.complete(transaction_id)
    
    return payout

