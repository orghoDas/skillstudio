"""
Live Streaming API Views
REST API endpoints for live sessions, chat, polls, recordings, and attendance.
"""

from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from live.models import (
    LiveSession, SessionParticipant, LiveChatMessage, LiveQuestion,
    LivePoll, PollOption, SessionRecording, RecordingView, SessionAttendance
)
from live.serializers import (
    LiveSessionSerializer, CreateLiveSessionSerializer,
    SessionParticipantSerializer, LiveChatMessageSerializer,
    SendChatMessageSerializer, LiveQuestionSerializer, AskQuestionSerializer,
    AnswerQuestionSerializer, LivePollSerializer, CreatePollSerializer,
    VotePollSerializer, PollResultsSerializer, SessionRecordingSerializer,
    CreateRecordingSerializer, RecordingViewSerializer,
    TrackRecordingViewSerializer, SessionAttendanceSerializer,
    SessionAnalyticsSerializer, JoinSessionSerializer
)
from live import services
from accounts.permissions import IsInstructor


# Live Session Views

class LiveSessionListView(generics.ListAPIView):
    """List all live sessions or sessions for a specific course."""
    
    serializer_class = LiveSessionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        from django.db.models import Count, Q
        from django.utils import timezone
        
        # Auto-update session statuses based on time
        now = timezone.now()
        
        # Update scheduled sessions that should be live
        LiveSession.objects.filter(
            status='scheduled',
            scheduled_start__lte=now,
            scheduled_end__gt=now
        ).update(status='live', actual_start=now)
        
        # Update live sessions that should be ended
        LiveSession.objects.filter(
            status='live',
            scheduled_end__lte=now
        ).update(status='ended', actual_end=now)
        
        queryset = LiveSession.objects.select_related(
            'course', 'instructor'
        ).prefetch_related(
            'participants'
        ).annotate(
            participants_joined=Count('participants', filter=Q(participants__status='joined'))
        )
        
        # Filter by course if provided
        course_id = self.request.query_params.get('course')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by instructor
        instructor_id = self.request.query_params.get('instructor')
        if instructor_id:
            queryset = queryset.filter(instructor_id=instructor_id)
        
        return queryset.order_by('-scheduled_start')


class CreateLiveSessionView(generics.CreateAPIView):
    """Create a new live session (instructors only)."""
    
    serializer_class = CreateLiveSessionSerializer
    permission_classes = [IsAuthenticated, IsInstructor]
    
    def perform_create(self, serializer):
        course = serializer.validated_data['course']
        
        # Use service to create session
        session = services.create_live_session(
            course=course,
            instructor=self.request.user,
            title=serializer.validated_data['title'],
            scheduled_start=serializer.validated_data['scheduled_start'],
            scheduled_end=serializer.validated_data['scheduled_end'],
            description=serializer.validated_data.get('description', ''),
            session_type=serializer.validated_data.get('session_type', 'class'),
            timezone_info=serializer.validated_data.get('timezone_info', 'UTC'),
            platform=serializer.validated_data.get('platform', 'agora'),
            meeting_link=serializer.validated_data.get('meeting_link', ''),
            meeting_id=serializer.validated_data.get('meeting_id', ''),
            meeting_password=serializer.validated_data.get('meeting_password', ''),
            max_participants=serializer.validated_data.get('max_participants'),
            enable_chat=serializer.validated_data.get('enable_chat', True),
            enable_qa=serializer.validated_data.get('enable_qa', True),
            enable_polls=serializer.validated_data.get('enable_polls', True),
            enable_recording=serializer.validated_data.get('enable_recording', True),
            enable_screen_share=serializer.validated_data.get('enable_screen_share', True),
            requires_enrollment=serializer.validated_data.get('requires_enrollment', True),
            is_public=serializer.validated_data.get('is_public', False),
            password_protected=serializer.validated_data.get('password_protected', False),
        )
        
        return session


class LiveSessionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a live session."""
    
    serializer_class = LiveSessionSerializer
    permission_classes = [IsAuthenticated]
    queryset = LiveSession.objects.select_related('course', 'instructor')
    
    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return CreateLiveSessionSerializer
        return LiveSessionSerializer


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def start_session(request, session_id):
    """Start a live session (instructor only)."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    try:
        updated_session = services.start_live_session(session, request.user)
        serializer = LiveSessionSerializer(updated_session)
        return Response({
            'session': serializer.data,
            'message': 'Session started successfully'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def end_session(request, session_id):
    """End a live session (instructor only)."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    try:
        updated_session = services.end_live_session(session, request.user)
        serializer = LiveSessionSerializer(updated_session)
        return Response({
            'session': serializer.data,
            'message': 'Session ended successfully'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# Session Participation Views

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_session(request, session_id):
    """Join a live session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    try:
        participant = services.join_session(session, request.user)
        serializer = SessionParticipantSerializer(participant)
        return Response({
            'participant': serializer.data,
            'session': LiveSessionSerializer(session).data,
            'message': 'Joined session successfully'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_session(request, session_id):
    """Leave a live session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    try:
        participant = services.leave_session(session, request.user)
        serializer = SessionParticipantSerializer(participant)
        return Response({
            'participant': serializer.data,
            'message': 'Left session successfully'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_participants(request, session_id):
    """Get all participants of a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    participants = SessionParticipant.objects.filter(
        session=session
    ).select_related('user', 'user__profile').order_by('-joined_at')
    
    serializer = SessionParticipantSerializer(participants, many=True, context={'request': request})
    return Response({
        'results': serializer.data,
        'count': participants.count()
    })


# Streaming Control Views

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_streaming(request, session_id):
    """Start streaming for a session (instructor only)."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    # Check if user is the instructor
    if session.instructor != request.user:
        return Response(
            {'error': 'Only the instructor can start streaming'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    stream_type = request.data.get('stream_type', 'camera')  # 'camera', 'screen', or 'both'
    
    session.is_streaming = True
    session.stream_type = stream_type
    session.save(update_fields=['is_streaming', 'stream_type'])
    
    return Response({
        'message': 'Streaming started',
        'is_streaming': True,
        'stream_type': stream_type
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stop_streaming(request, session_id):
    """Stop streaming for a session (instructor only)."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    # Check if user is the instructor
    if session.instructor != request.user:
        return Response(
            {'error': 'Only the instructor can stop streaming'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    session.is_streaming = False
    session.stream_type = ''
    session.save(update_fields=['is_streaming', 'stream_type'])
    
    return Response({
        'message': 'Streaming stopped',
        'is_streaming': False
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def streaming_status(request, session_id):
    """Get streaming status for a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    # Get instructor name from profile if available
    instructor_name = session.instructor.email
    if hasattr(session.instructor, 'profile') and session.instructor.profile:
        profile = session.instructor.profile
        full_name = f"{profile.first_name or ''} {profile.last_name or ''}".strip()
        instructor_name = full_name or session.instructor.username or session.instructor.email
    elif session.instructor.username:
        instructor_name = session.instructor.username
    
    return Response({
        'is_streaming': session.is_streaming,
        'stream_type': session.stream_type,
        'instructor': session.instructor.id,
        'instructor_name': instructor_name
    })


# Chat Views

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_chat_messages(request, session_id):
    """Get chat messages for a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    messages = LiveChatMessage.objects.filter(
        session=session,
        is_deleted=False
    ).select_related('user', 'reply_to').order_by('created_at')
    
    # Limit to recent messages
    limit = int(request.query_params.get('limit', 100))
    messages = messages[:limit]
    
    serializer = LiveChatMessageSerializer(messages, many=True)
    return Response({
        'messages': serializer.data,
        'total': messages.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_chat_message(request, session_id):
    """Send a chat message in a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    serializer = SendChatMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        reply_to = None
        if serializer.validated_data.get('reply_to'):
            reply_to = LiveChatMessage.objects.get(
                id=serializer.validated_data['reply_to'],
                session=session
            )
        
        message = services.send_chat_message(
            session=session,
            user=request.user,
            content=serializer.validated_data['content'],
            message_type=serializer.validated_data.get('message_type', 'text'),
            reply_to=reply_to
        )
        
        response_serializer = LiveChatMessageSerializer(message)
        return Response({
            'message': response_serializer.data
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# Q&A Views

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_questions(request, session_id):
    """Get Q&A questions for a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    questions = LiveQuestion.objects.filter(
        session=session
    ).select_related('user', 'answered_by').order_by('-upvotes', '-created_at')
    
    # Filter by status if provided
    status_filter = request.query_params.get('status')
    if status_filter:
        questions = questions.filter(status=status_filter)
    
    serializer = LiveQuestionSerializer(questions, many=True)
    return Response({
        'questions': serializer.data,
        'total': questions.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ask_question(request, session_id):
    """Ask a question in a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    serializer = AskQuestionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        question = services.ask_question(
            session=session,
            user=request.user,
            question=serializer.validated_data['question'],
            is_anonymous=serializer.validated_data.get('is_anonymous', False)
        )
        
        response_serializer = LiveQuestionSerializer(question)
        return Response({
            'question': response_serializer.data
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def answer_question(request, question_id):
    """Answer a question (instructor only)."""
    question = get_object_or_404(LiveQuestion, id=question_id)
    
    serializer = AnswerQuestionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        updated_question = services.answer_question(
            question=question,
            user=request.user,
            answer=serializer.validated_data['answer']
        )
        
        response_serializer = LiveQuestionSerializer(updated_question)
        return Response({
            'question': response_serializer.data,
            'message': 'Question answered successfully'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upvote_question(request, question_id):
    """Upvote a question."""
    question = get_object_or_404(LiveQuestion, id=question_id)
    
    try:
        updated_question = services.upvote_question(question, request.user)
        serializer = LiveQuestionSerializer(updated_question)
        return Response({
            'question': serializer.data,
            'message': 'Question upvoted'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# Poll Views

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_polls(request, session_id):
    """Get polls for a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    polls = LivePoll.objects.filter(
        session=session
    ).prefetch_related('options').order_by('-created_at')
    
    serializer = LivePollSerializer(polls, many=True)
    return Response({
        'polls': serializer.data,
        'total': polls.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def create_poll(request, session_id):
    """Create a poll in a session (instructor only)."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    serializer = CreatePollSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        poll = services.create_poll(
            session=session,
            user=request.user,
            question=serializer.validated_data['question'],
            options=serializer.validated_data['options'],
            description=serializer.validated_data.get('description', ''),
            allow_multiple_answers=serializer.validated_data.get('allow_multiple_answers', False),
            show_results_immediately=serializer.validated_data.get('show_results_immediately', True),
            is_anonymous=serializer.validated_data.get('is_anonymous', False),
            duration_seconds=serializer.validated_data.get('duration_seconds')
        )
        
        response_serializer = LivePollSerializer(poll)
        return Response({
            'poll': response_serializer.data
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def start_poll(request, poll_id):
    """Start a poll (instructor only)."""
    poll = get_object_or_404(LivePoll, id=poll_id)
    
    duration = request.data.get('duration_seconds')
    
    try:
        updated_poll = services.start_poll(poll, request.user, duration)
        serializer = LivePollSerializer(updated_poll)
        return Response({
            'poll': serializer.data,
            'message': 'Poll started'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def close_poll(request, poll_id):
    """Close a poll (instructor only)."""
    poll = get_object_or_404(LivePoll, id=poll_id)
    
    try:
        updated_poll = services.close_poll(poll, request.user)
        serializer = LivePollSerializer(updated_poll)
        return Response({
            'poll': serializer.data,
            'message': 'Poll closed'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vote_poll(request, poll_id):
    """Vote on a poll."""
    poll = get_object_or_404(LivePoll, id=poll_id)
    
    serializer = VotePollSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        services.vote_poll(
            poll=poll,
            user=request.user,
            option_ids=serializer.validated_data['option_ids']
        )
        
        # Return updated poll results
        results = services.get_poll_results(poll)
        return Response({
            'results': results,
            'message': 'Vote recorded'
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def poll_results(request, poll_id):
    """Get poll results."""
    poll = get_object_or_404(LivePoll, id=poll_id)
    
    results = services.get_poll_results(poll)
    return Response(results)


# Recording Views

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_recordings(request, session_id):
    """Get recordings for a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    recordings = SessionRecording.objects.filter(
        session=session,
        processing_status='ready'
    ).order_by('-recorded_at')
    
    serializer = SessionRecordingSerializer(recordings, many=True)
    return Response({
        'recordings': serializer.data,
        'total': recordings.count()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsInstructor])
def create_recording(request, session_id):
    """Create a recording for a session (instructor only)."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    serializer = CreateRecordingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        recording = services.create_recording(
            session=session,
            video_url=serializer.validated_data['video_url'],
            title=serializer.validated_data.get('title'),
            description=serializer.validated_data.get('description', ''),
            thumbnail_url=serializer.validated_data.get('thumbnail_url', ''),
            duration_seconds=serializer.validated_data.get('duration_seconds', 0),
            file_size_mb=serializer.validated_data.get('file_size_mb', 0),
            is_public=serializer.validated_data.get('is_public', False),
            requires_enrollment=serializer.validated_data.get('requires_enrollment', True)
        )
        
        response_serializer = SessionRecordingSerializer(recording)
        return Response({
            'recording': response_serializer.data
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recording_detail(request, recording_id):
    """Get recording details."""
    recording = get_object_or_404(SessionRecording, id=recording_id)
    
    serializer = SessionRecordingSerializer(recording)
    return Response({
        'recording': serializer.data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_recording_view(request, recording_id):
    """Track user viewing a recording."""
    recording = get_object_or_404(SessionRecording, id=recording_id)
    
    serializer = TrackRecordingViewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    try:
        view = services.track_recording_view(
            recording=recording,
            user=request.user,
            watch_duration_seconds=serializer.validated_data['watch_duration_seconds'],
            last_position_seconds=serializer.validated_data['last_position_seconds']
        )
        
        response_serializer = RecordingViewSerializer(view)
        return Response({
            'view': response_serializer.data
        })
    except Exception as e:
        return Response({
            'error': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)


# Attendance Views

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def session_attendance(request, session_id):
    """Get attendance records for a session."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    # Only instructor can view full attendance
    if session.instructor != request.user:
        return Response({
            'error': 'Only instructor can view attendance'
        }, status=status.HTTP_403_FORBIDDEN)
    
    attendance = SessionAttendance.objects.filter(
        session=session
    ).select_related('participant', 'participant__user').order_by(
        '-marked_present', 'participant__user__email'
    )
    
    serializer = SessionAttendanceSerializer(attendance, many=True)
    return Response({
        'attendance': serializer.data,
        'total': attendance.count(),
        'present': attendance.filter(marked_present=True).count()
    })


# Analytics Views

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsInstructor])
def session_analytics(request, session_id):
    """Get comprehensive analytics for a session (instructor only)."""
    session = get_object_or_404(LiveSession, id=session_id)
    
    if session.instructor != request.user:
        return Response({
            'error': 'Only instructor can view analytics'
        }, status=status.HTTP_403_FORBIDDEN)
    
    analytics = services.get_session_analytics(session)
    serializer = SessionAnalyticsSerializer(analytics)
    
    return Response(serializer.data)


# Upcoming Sessions

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def upcoming_sessions(request):
    """Get upcoming live sessions for user's enrolled courses."""
    sessions = services.get_upcoming_sessions(request.user, limit=10)
    serializer = LiveSessionSerializer(sessions, many=True)
    
    return Response({
        'sessions': serializer.data,
        'total': sessions.count()
    })


# User History

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_session_history(request):
    """Get user's live session participation history."""
    history = services.get_user_session_history(request.user, limit=20)
    serializer = SessionParticipantSerializer(history, many=True)
    
    return Response({
        'history': serializer.data,
        'total': history.count()
    })
