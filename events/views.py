from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

from .models import Event, EventRegistration, EventFeedback, EventResource
from .serializers import (
    EventSerializer, EventListSerializer, EventDetailSerializer,
    EventRegistrationSerializer, EventFeedbackSerializer,
    EventResourceSerializer
)
from .services import (
    register_for_event, cancel_event_registration,
    mark_attendance, submit_event_feedback,
    get_event_analytics, get_upcoming_events,
    add_event_resource, can_access_event_resource
)
from accounts.permissions import IsInstructor


# ===========================
# 📅 Event Management Views
# ===========================

class EventListCreateView(generics.ListCreateAPIView):
    """List all events or create new event (instructors only)."""
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return EventSerializer
        return EventListSerializer
    
    def get_queryset(self):
        queryset = Event.objects.all()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        else:
            # Default: show only published events for students
            if self.request.user.role != 'instructor':
                queryset = queryset.filter(status='published')
        
        # Filter by type
        event_type = self.request.query_params.get('type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        
        # Filter by upcoming/past
        time_filter = self.request.query_params.get('time')
        if time_filter == 'upcoming':
            queryset = queryset.filter(scheduled_for__gt=timezone.now())
        elif time_filter == 'past':
            queryset = queryset.filter(scheduled_for__lt=timezone.now())
        
        # Filter by course
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        # Filter by host
        if self.request.user.role == 'instructor':
            my_events = self.request.query_params.get('my_events')
            if my_events == 'true':
                queryset = queryset.filter(host=self.request.user)
        
        return queryset.order_by('-scheduled_for')
    
    def perform_create(self, serializer):
        serializer.save(host=self.request.user)


class EventDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete an event."""
    permission_classes = [IsAuthenticated]
    queryset = Event.objects.all()
    
    def get_serializer_class(self):
        if self.request.method == 'GET':
            return EventDetailSerializer
        return EventSerializer


# ===========================
# 🎫 Event Registration Views
# ===========================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_event(request, event_id):
    """Register for an event."""
    from django.core.exceptions import ValidationError, PermissionDenied
    
    event = get_object_or_404(Event, id=event_id)
    
    try:
        registration = register_for_event(event, request.user)
        serializer = EventRegistrationSerializer(registration)
        
        return Response({
            'registration': serializer.data,
            'message': 'Successfully registered for event'
        }, status=status.HTTP_201_CREATED)
        
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_registration(request, registration_id):
    """Cancel event registration."""
    registration = get_object_or_404(
        EventRegistration,
        id=registration_id,
        user=request.user
    )
    
    try:
        updated = cancel_event_registration(registration)
        serializer = EventRegistrationSerializer(updated)
        
        return Response({
            'registration': serializer.data,
            'message': 'Registration cancelled successfully'
        })
        
    except ValueError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_registrations(request):
    """Get user's event registrations."""
    registrations = EventRegistration.objects.filter(
        user=request.user
    ).select_related('event').order_by('-registered_on')
    
    # Filter by status
    status_filter = request.query_params.get('status')
    if status_filter:
        registrations = registrations.filter(status=status_filter)
    
    serializer = EventRegistrationSerializer(registrations, many=True)
    return Response({
        'registrations': serializer.data,
        'total': registrations.count()
    })


# ===========================
# 📝 Event Feedback Views
# ===========================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_feedback(request, event_id):
    """Submit feedback for an event."""
    from django.core.exceptions import ValidationError, PermissionDenied
    
    event = get_object_or_404(Event, id=event_id)
    
    rating = request.data.get('rating')
    if not rating:
        return Response({
            'error': 'Rating is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        rating = int(rating)
        feedback = submit_event_feedback(
            event,
            request.user,
            rating,
            title=request.data.get('title', ''),
            comment=request.data.get('comment', ''),
            content_quality=request.data.get('content_quality'),
            host_performance=request.data.get('host_performance'),
            would_recommend=request.data.get('would_recommend', True)
        )
        
        serializer = EventFeedbackSerializer(feedback)
        return Response({
            'feedback': serializer.data,
            'message': 'Feedback submitted successfully'
        }, status=status.HTTP_201_CREATED)
    
    except ValidationError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except PermissionDenied as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_403_FORBIDDEN)
    except ValueError as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_feedbacks(request, event_id):
    """Get all feedbacks for an event."""
    event = get_object_or_404(Event, id=event_id)
    feedbacks = event.feedbacks.all().order_by('-created_at')
    
    serializer = EventFeedbackSerializer(feedbacks, many=True)
    return Response({
        'feedbacks': serializer.data,
        'total': feedbacks.count()
    })


# ===========================
# 📊 Event Analytics Views (Instructors)
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsInstructor])
def event_analytics_view(request, event_id):
    """Get analytics for an event."""
    event = get_object_or_404(Event, id=event_id, host=request.user)
    
    analytics = get_event_analytics(event)
    return Response(analytics)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsInstructor])
def event_registrations_list(request, event_id):
    """Get all registrations for an event (instructor view)."""
    event = get_object_or_404(Event, id=event_id, host=request.user)
    
    registrations = event.registrations.all().select_related('user')
    serializer = EventRegistrationSerializer(registrations, many=True)
    
    return Response({
        'registrations': serializer.data,
        'total': registrations.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def mark_user_attendance(request, registration_id):
    """Mark a user as attended."""
    registration = get_object_or_404(
        EventRegistration,
        id=registration_id,
        event__host=request.user
    )
    
    mark_attendance(
        registration,
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT')
    )
    
    serializer = EventRegistrationSerializer(registration)
    return Response({
        'registration': serializer.data,
        'message': 'Attendance marked successfully'
    })


# ===========================
# 📚 Event Resources Views
# ===========================

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def upload_event_resource(request, event_id):
    """Upload a resource for an event."""
    event = get_object_or_404(Event, id=event_id, host=request.user)
    
    serializer = EventResourceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save(event=event)
    
    return Response({
        'resource': serializer.data,
        'message': 'Resource uploaded successfully'
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def event_resources_list(request, event_id):
    """Get resources for an event."""
    event = get_object_or_404(Event, id=event_id)
    
    # Filter resources based on access
    resources = event.resources.all()
    
    # Filter accessible resources
    accessible = []
    for resource in resources:
        if can_access_event_resource(resource, request.user):
            accessible.append(resource)
    
    serializer = EventResourceSerializer(accessible, many=True)
    return Response({
        'resources': serializer.data,
        'total': len(accessible)
    })


# ===========================
# 🔍 Discovery Views
# ===========================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def upcoming_events_view(request):
    """Get upcoming events."""
    limit = int(request.query_params.get('limit', 10))
    events = get_upcoming_events(user=request.user, limit=limit)
    
    serializer = EventListSerializer(events, many=True)
    return Response({
        'events': serializer.data,
        'total': events.count()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def featured_events_view(request):
    """Get featured events."""
    events = Event.objects.filter(
        status='published',
        is_featured=True,
        scheduled_for__gt=timezone.now()
    ).order_by('scheduled_for')[:5]
    
    serializer = EventListSerializer(events, many=True)
    return Response({
        'events': serializer.data
    })
