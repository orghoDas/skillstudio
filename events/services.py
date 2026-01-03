from django.utils import timezone
from django.db import transaction
from django.db.models import Avg, Q
from django.core.exceptions import ValidationError, PermissionDenied
from decimal import Decimal

from .models import Event, EventRegistration, EventFeedback, EventAttendanceLog, EventResource


@transaction.atomic
def register_for_event(event, user):
    """
    Register a user for an event.
    
    Args:
        event: Event instance
        user: User instance
    
    Returns:
        EventRegistration instance
    
    Raises:
        ValidationError: If event is full, past, or user already registered
        PermissionDenied: If user lacks required enrollment
    """
    # Check if event is past
    if event.is_past():
        raise ValidationError("Cannot register for past events")
    
    # Check if event is cancelled
    if event.status == 'cancelled':
        raise ValidationError("Event has been cancelled")
    
    # Check if event is published
    if event.status != 'published':
        raise PermissionDenied("Event is not published")
    
    # Check if already registered
    if EventRegistration.objects.filter(event=event, user=user).exists():
        raise ValidationError("You are already registered for this event")
    
    # Check if event is full
    if event.is_full():
        raise ValidationError("Event is full")
    
    # Check course enrollment if required
    if event.requires_enrollment and event.course:
        from enrollments.models import Enrollment
        if not Enrollment.objects.filter(user=user, course=event.course, status='active').exists():
            raise PermissionDenied("You must be enrolled in the course to attend this event")
    
    # Determine payment amount
    payment_amount = event.price if not event.is_free else Decimal('0.00')
    
    # Create registration
    registration = EventRegistration.objects.create(
        event=event,
        user=user,
        payment_amount=payment_amount,
        payment_status='completed' if event.is_free else 'pending',
        status='confirmed' if event.is_free else 'pending'
    )
    
    return registration


@transaction.atomic
def cancel_event_registration(registration, reason=None):
    """
    Cancel an event registration.
    
    Args:
        registration: EventRegistration instance
        reason: Optional cancellation reason
    
    Returns:
        Updated EventRegistration instance
    
    Raises:
        ValidationError: If event is past or registration already cancelled
    """
    if registration.status == 'cancelled':
        raise ValidationError("Registration is already cancelled")
    
    if registration.event.is_past():
        raise ValidationError("Cannot cancel registration for past events")
    
    registration.status = 'cancelled'
    registration.cancelled_at = timezone.now()
    registration.save(update_fields=['status', 'cancelled_at'])
    
    # TODO: Process refund if applicable
    
    return registration


def mark_attendance(registration, ip_address=None, user_agent=None):
    """
    Mark user as attended for an event.
    
    Args:
        registration: EventRegistration instance
        ip_address: Optional IP address
        user_agent: Optional user agent
    
    Returns:
        EventAttendanceLog instance
    """
    registration.attended = True
    registration.attended_at = timezone.now()
    registration.status = 'attended'
    registration.save()
    
    # Create attendance log
    log = EventAttendanceLog.objects.create(
        registration=registration,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return log


@transaction.atomic
def submit_event_feedback(event, user, rating, **kwargs):
    """
    Submit feedback for an event.
    
    Args:
        event: Event instance
        user: User instance
        rating: Overall rating (1-5)
        **kwargs: Additional feedback fields
    
    Returns:
        EventFeedback instance
    
    Raises:
        ValidationError: If user didn't attend or feedback already exists
        PermissionDenied: If user cannot provide feedback
    """
    # Validate rating
    if rating < 1 or rating > 5:
        raise ValidationError("Rating must be between 1 and 5")
    
    # Check if user attended
    registration = EventRegistration.objects.filter(
        event=event,
        user=user
    ).first()
    
    if not registration:
        raise PermissionDenied("You must be registered for the event to provide feedback")
    
    if not registration.attended:
        raise ValidationError("You must attend the event to provide feedback")
    
    # Check if event is past
    if not event.is_past():
        raise ValidationError("Cannot provide feedback for upcoming events")
    
    # Check if feedback already exists
    if EventFeedback.objects.filter(event=event, user=user).exists():
        raise ValidationError("You have already provided feedback for this event")
    
    # Create feedback
    feedback = EventFeedback.objects.create(
        event=event,
        user=user,
        rating=rating,
        title=kwargs.get('title', ''),
        comment=kwargs.get('comment', ''),
        content_quality=kwargs.get('content_quality'),
        host_performance=kwargs.get('host_performance'),
        would_recommend=kwargs.get('would_recommend', True)
    )
    
    return feedback


def get_event_analytics(event):
    """
    Get analytics for an event.
    
    Args:
        event: Event instance
    
    Returns:
        Dictionary with analytics data
    """
    registrations = event.registrations.all()
    total_registered = registrations.count()
    confirmed = registrations.filter(status='confirmed').count()
    attended = registrations.filter(attended=True).count()
    cancelled = registrations.filter(status='cancelled').count()
    
    # Attendance rate
    attendance_rate = (attended / confirmed * 100) if confirmed > 0 else 0
    
    # Feedback analytics
    feedbacks = event.feedbacks.all()
    avg_rating = feedbacks.aggregate(Avg('rating'))['rating__avg'] or 0
    avg_content = feedbacks.aggregate(Avg('content_quality'))['content_quality__avg'] or 0
    avg_host = feedbacks.aggregate(Avg('host_performance'))['host_performance__avg'] or 0
    
    recommend_count = feedbacks.filter(would_recommend=True).count()
    recommend_rate = (recommend_count / feedbacks.count() * 100) if feedbacks.count() > 0 else 0
    
    return {
        'total_registrations': total_registered,
        'confirmed_count': confirmed,
        'attended_count': attended,
        'cancelled_count': cancelled,
        'attendance_rate': f"{attendance_rate:.2f}",
        'average_rating': round(avg_rating, 2),
        'average_content_quality': round(avg_content, 2),
        'average_host_performance': round(avg_host, 2),
        'recommendation_rate': round(recommend_rate, 2),
        'total_feedback': feedbacks.count()
    }


def get_upcoming_events(user=None, limit=10):
    """
    Get upcoming events, optionally filtered by user enrollment.
    
    Args:
        user: Optional User instance
        limit: Number of events to return
    
    Returns:
        QuerySet of Event instances
    """
    events = Event.objects.filter(
        status='published',
        start_time__gt=timezone.now()
    ).order_by('start_time')
    
    if user and user.is_authenticated:
        # Filter by enrolled courses if specified
        from enrollments.models import Enrollment
        enrolled_courses = Enrollment.objects.filter(
            user=user,
            status='active'
        ).values_list('course_id', flat=True)
        
        # Get events for enrolled courses or free events
        events = events.filter(
            Q(course_id__in=enrolled_courses) | Q(course__isnull=True)
        )
    
    return events[:limit]


def add_event_resource(event, title, resource_type, **kwargs):
    """
    Add a resource to an event.
    
    Args:
        event: Event instance
        title: Resource title
        resource_type: Type of resource
        **kwargs: Additional resource fields
    
    Returns:
        EventResource instance
    """
    resource = EventResource.objects.create(
        event=event,
        title=title,
        resource_type=resource_type,
        description=kwargs.get('description', ''),
        file=kwargs.get('file'),
        url=kwargs.get('url', ''),
        available_after_event=kwargs.get('available_after_event', True),
        attendees_only=kwargs.get('attendees_only', True)
    )
    
    return resource


def can_access_event_resource(resource, user):
    """
    Check if user can access an event resource.
    
    Args:
        resource: EventResource instance
        user: User instance
    
    Returns:
        Boolean indicating access permission
    """
    event = resource.event
    
    # Check if resource is available
    if not resource.available_after_event and not event.is_past():
        return False
    
    # Check if attendees only
    if resource.attendees_only:
        registration = EventRegistration.objects.filter(
            event=event,
            user=user,
            attended=True
        ).exists()
        return registration
    
    # Check if user registered
    return EventRegistration.objects.filter(
        event=event,
        user=user,
        status__in=['confirmed', 'attended']
    ).exists()


from django.db import models  # Import for Q object