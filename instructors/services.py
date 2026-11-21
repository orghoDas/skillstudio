from django.db import models, transaction
from django.db.models import Count, Max, Sum, Q
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal

from courses.models import Course
from enrollments.models import Enrollment, LessonProgress
from payments.models import Payment, Payout
from .models import InstructorProfile


def get_course_overview(instructor):
    """Get course overview with enrollment and rating statistics."""
    return (
        Course.objects
        .filter(instructor=instructor)
        .annotate(
            total_enrollments=Count("enrollments"),
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


def get_revenue_summary(instructor):
    """Revenue summary (wallet-ledger based, PAY-07) and payout history."""
    from payments.services import calculate_instructor_balance

    balance = calculate_instructor_balance(instructor)
    fees = Payment.objects.filter(
        instructor=instructor,
        purpose=Payment.PURPOSE_COURSE_PURCHASE,
        status__in=("completed", "partially_refunded"),
    ).aggregate(platform_fee=Sum("platform_fee"))
    earnings = {
        "total_earned": balance["total_earnings"],   # net of refunds
        "platform_fee": fees["platform_fee"] or 0,
        "available": balance["available"],           # withdrawable wallet balance
        "pending_payouts": balance["pending"],
        "paid_out": balance["paid_out"],
    }

    payouts = (
        Payout.objects
        .filter(instructor=instructor)
        .order_by("-created_at")
    )

    return earnings, payouts


def get_or_create_instructor_profile(user):
    """
    Get or create instructor profile for a user.
    
    Args:
        user: User instance
    
    Returns:
        InstructorProfile instance
    """
    profile, _ = InstructorProfile.objects.get_or_create(user=user)
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

