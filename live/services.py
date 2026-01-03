"""
Live Streaming Services
Business logic for live streaming sessions, chat, polls, and recordings.
"""

from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q, Count, Avg, Sum, F
from datetime import timedelta
import uuid
import hashlib


def generate_stream_key():
    """Generate a unique stream key for live sessions."""
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]


def generate_channel_name(session_id):
    """Generate a channel name for streaming."""
    return f"session_{session_id}_{uuid.uuid4().hex[:8]}"


def create_live_session(
    course,
    instructor,
    title,
    scheduled_start,
    scheduled_end,
    **kwargs
):
    """
    Create a new live streaming session.
    
    Args:
        course: Course instance
        instructor: User instance (instructor)
        title: Session title
        scheduled_start: DateTime when session starts
        scheduled_end: DateTime when session ends
        **kwargs: Additional session parameters
    
    Returns:
        LiveSession instance
    """
    from live.models import LiveSession
    
    # Validate instructor owns the course
    if course.instructor != instructor:
        raise PermissionDenied("Only course instructor can create live sessions")
    
    # Validate schedule
    if scheduled_start >= scheduled_end:
        raise ValidationError("Start time must be before end time")
    
    if scheduled_start < timezone.now():
        raise ValidationError("Cannot schedule session in the past")
    
    # Check for overlapping sessions
    overlapping = LiveSession.objects.filter(
        instructor=instructor,
        status__in=['scheduled', 'live'],
        scheduled_start__lt=scheduled_end,
        scheduled_end__gt=scheduled_start
    ).exists()
    
    if overlapping:
        raise ValidationError("You have overlapping sessions scheduled")
    
    # Generate streaming credentials
    stream_key = generate_stream_key()
    channel_name = generate_channel_name(uuid.uuid4())
    
    session = LiveSession.objects.create(
        course=course,
        instructor=instructor,
        title=title,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        stream_key=stream_key,
        channel_name=channel_name,
        **kwargs
    )
    
    return session


def start_live_session(session, user):
    """
    Start a live session (change status to 'live').
    
    Args:
        session: LiveSession instance
        user: User starting the session (must be instructor)
    
    Returns:
        Updated LiveSession instance
    """
    if session.instructor != user:
        raise PermissionDenied("Only instructor can start the session")
    
    if session.status == 'live':
        raise ValidationError("Session is already live")
    
    if session.status == 'ended':
        raise ValidationError("Cannot restart ended session")
    
    session.status = 'live'
    session.actual_start = timezone.now()
    session.save(update_fields=['status', 'actual_start'])
    
    return session


def end_live_session(session, user):
    """
    End a live session.
    
    Args:
        session: LiveSession instance
        user: User ending the session (must be instructor)
    
    Returns:
        Updated LiveSession instance
    """
    if session.instructor != user:
        raise PermissionDenied("Only instructor can end the session")
    
    if session.status != 'live':
        raise ValidationError("Session is not currently live")
    
    session.status = 'ended'
    session.actual_end = timezone.now()
    session.save(update_fields=['status', 'actual_end'])
    
    # Mark all participants as left
    from live.models import SessionParticipant
    SessionParticipant.objects.filter(
        session=session,
        status='joined'
    ).update(status='left', left_at=timezone.now())
    
    # Process attendance
    process_session_attendance(session)
    
    return session


def join_session(session, user):
    """
    User joins a live session.
    
    Args:
        session: LiveSession instance
        user: User joining
    
    Returns:
        SessionParticipant instance
    """
    from live.models import SessionParticipant
    
    # Check if session is live
    if session.status != 'live':
        raise ValidationError("Session is not currently live")
    
    # Check enrollment requirement
    if session.requires_enrollment:
        from enrollments.models import Enrollment
        if not Enrollment.objects.filter(
            user=user,
            course=session.course,
            status='active'
        ).exists():
            raise PermissionDenied("You must be enrolled in the course to join")
    
    # Check capacity
    if session.max_participants:
        current_count = session.participant_count()
        if current_count >= session.max_participants:
            raise ValidationError("Session is at maximum capacity")
    
    # Get or create participant
    participant, created = SessionParticipant.objects.get_or_create(
        session=session,
        user=user,
        defaults={
            'status': 'joined',
            'joined_at': timezone.now()
        }
    )
    
    if not created:
        if participant.status == 'banned':
            raise PermissionDenied("You are banned from this session")
        
        # Rejoin
        participant.status = 'joined'
        participant.joined_at = timezone.now()
        participant.save(update_fields=['status', 'joined_at'])
    
    return participant


def leave_session(session, user):
    """
    User leaves a live session.
    
    Args:
        session: LiveSession instance
        user: User leaving
    
    Returns:
        Updated SessionParticipant instance
    """
    from live.models import SessionParticipant
    
    try:
        participant = SessionParticipant.objects.get(session=session, user=user)
    except SessionParticipant.DoesNotExist:
        raise ValidationError("You are not in this session")
    
    if participant.status != 'joined':
        raise ValidationError("You are not currently in the session")
    
    participant.status = 'left'
    participant.left_at = timezone.now()
    
    # Calculate duration
    if participant.joined_at:
        duration = (timezone.now() - participant.joined_at).total_seconds()
        participant.duration_seconds += int(duration)
    
    participant.save(update_fields=['status', 'left_at', 'duration_seconds'])
    
    return participant


def send_chat_message(session, user, content, message_type='text', reply_to=None):
    """
    Send a chat message in a live session.
    
    Args:
        session: LiveSession instance
        user: User sending message
        content: Message content
        message_type: Type of message (text, emoji, file, system)
        reply_to: Optional message being replied to
    
    Returns:
        LiveChatMessage instance
    """
    from live.models import LiveChatMessage, SessionParticipant
    
    # Check if chat is enabled
    if not session.enable_chat:
        raise ValidationError("Chat is disabled for this session")
    
    # Check if user is participant
    if not SessionParticipant.objects.filter(
        session=session,
        user=user,
        status='joined'
    ).exists():
        raise PermissionDenied("You must be in the session to send messages")
    
    # Create message
    message = LiveChatMessage.objects.create(
        session=session,
        user=user,
        content=content,
        message_type=message_type,
        reply_to=reply_to
    )
    
    # Update participant stats
    SessionParticipant.objects.filter(
        session=session,
        user=user
    ).update(chat_messages_count=F('chat_messages_count') + 1)
    
    return message


def ask_question(session, user, question, is_anonymous=False):
    """
    Ask a question during a live session.
    
    Args:
        session: LiveSession instance
        user: User asking question
        question: Question text
        is_anonymous: Whether to post anonymously
    
    Returns:
        LiveQuestion instance
    """
    from live.models import LiveQuestion, SessionParticipant
    
    # Check if Q&A is enabled
    if not session.enable_qa:
        raise ValidationError("Q&A is disabled for this session")
    
    # Check if user is participant
    if not SessionParticipant.objects.filter(
        session=session,
        user=user,
        status='joined'
    ).exists():
        raise PermissionDenied("You must be in the session to ask questions")
    
    # Create question
    question_obj = LiveQuestion.objects.create(
        session=session,
        user=user,
        question=question,
        is_anonymous=is_anonymous
    )
    
    # Update participant stats
    SessionParticipant.objects.filter(
        session=session,
        user=user
    ).update(questions_asked=F('questions_asked') + 1)
    
    return question_obj


def answer_question(question, user, answer):
    """
    Answer a question (instructor only).
    
    Args:
        question: LiveQuestion instance
        user: User answering (must be instructor)
        answer: Answer text
    
    Returns:
        Updated LiveQuestion instance
    """
    if question.session.instructor != user:
        raise PermissionDenied("Only instructor can answer questions")
    
    question.answer = answer
    question.status = 'answered'
    question.answered_by = user
    question.answered_at = timezone.now()
    question.save(update_fields=['answer', 'status', 'answered_by', 'answered_at'])
    
    return question


def upvote_question(question, user):
    """
    Upvote a question to prioritize it.
    
    Args:
        question: LiveQuestion instance
        user: User upvoting
    
    Returns:
        Updated LiveQuestion instance
    """
    from live.models import SessionParticipant
    
    # Check if user is participant
    if not SessionParticipant.objects.filter(
        session=question.session,
        user=user,
        status='joined'
    ).exists():
        raise PermissionDenied("You must be in the session to upvote")
    
    # Simple upvote (no duplicate checking for simplicity)
    question.upvotes = F('upvotes') + 1
    question.save(update_fields=['upvotes'])
    question.refresh_from_db()
    
    return question


def create_poll(session, user, question, options, **kwargs):
    """
    Create a poll during live session.
    
    Args:
        session: LiveSession instance
        user: User creating poll (must be instructor)
        question: Poll question
        options: List of option texts
        **kwargs: Additional poll parameters
    
    Returns:
        LivePoll instance with options
    """
    from live.models import LivePoll, PollOption
    
    if session.instructor != user:
        raise PermissionDenied("Only instructor can create polls")
    
    if not session.enable_polls:
        raise ValidationError("Polls are disabled for this session")
    
    if len(options) < 2:
        raise ValidationError("Poll must have at least 2 options")
    
    with transaction.atomic():
        poll = LivePoll.objects.create(
            session=session,
            created_by=user,
            question=question,
            **kwargs
        )
        
        # Create options
        for idx, option_text in enumerate(options):
            PollOption.objects.create(
                poll=poll,
                text=option_text,
                order=idx
            )
    
    return poll


def start_poll(poll, user, duration_seconds=None):
    """
    Start/activate a poll.
    
    Args:
        poll: LivePoll instance
        user: User starting poll (must be instructor)
        duration_seconds: Optional poll duration
    
    Returns:
        Updated LivePoll instance
    """
    if poll.session.instructor != user:
        raise PermissionDenied("Only instructor can start polls")
    
    if poll.status == 'active':
        raise ValidationError("Poll is already active")
    
    poll.status = 'active'
    poll.started_at = timezone.now()
    
    if duration_seconds:
        poll.duration_seconds = duration_seconds
        poll.ends_at = timezone.now() + timedelta(seconds=duration_seconds)
    
    poll.save(update_fields=['status', 'started_at', 'duration_seconds', 'ends_at'])
    
    return poll


def close_poll(poll, user):
    """
    Close a poll.
    
    Args:
        poll: LivePoll instance
        user: User closing poll (must be instructor)
    
    Returns:
        Updated LivePoll instance
    """
    if poll.session.instructor != user:
        raise PermissionDenied("Only instructor can close polls")
    
    poll.status = 'closed'
    poll.save(update_fields=['status'])
    
    return poll


def vote_poll(poll, user, option_ids):
    """
    Vote on a poll.
    
    Args:
        poll: LivePoll instance
        user: User voting
        option_ids: List of option IDs (single ID if not multiple choice)
    
    Returns:
        List of PollVote instances
    """
    from live.models import PollVote, PollOption, SessionParticipant
    
    # Check if poll is active
    if not poll.is_active():
        raise ValidationError("Poll is not currently active")
    
    # Check if user is participant
    if not SessionParticipant.objects.filter(
        session=poll.session,
        user=user,
        status='joined'
    ).exists():
        raise PermissionDenied("You must be in the session to vote")
    
    # Check multiple answers setting
    if not poll.allow_multiple_answers and len(option_ids) > 1:
        raise ValidationError("This poll allows only one answer")
    
    # Check if already voted
    existing_votes = PollVote.objects.filter(poll=poll, user=user)
    if existing_votes.exists() and not poll.allow_multiple_answers:
        raise ValidationError("You have already voted on this poll")
    
    with transaction.atomic():
        # Delete existing votes if re-voting is allowed
        existing_votes.delete()
        
        # Create new votes
        votes = []
        for option_id in option_ids:
            try:
                option = PollOption.objects.get(id=option_id, poll=poll)
            except PollOption.DoesNotExist:
                raise ValidationError(f"Invalid option ID: {option_id}")
            
            vote = PollVote.objects.create(
                poll=poll,
                option=option,
                user=user
            )
            votes.append(vote)
            
            # Update option vote count
            option.votes_count = F('votes_count') + 1
            option.save(update_fields=['votes_count'])
        
        # Update participant stats
        SessionParticipant.objects.filter(
            session=poll.session,
            user=user
        ).update(polls_answered=F('polls_answered') + 1)
    
    return votes


def get_poll_results(poll):
    """
    Get poll results with vote counts and percentages.
    
    Args:
        poll: LivePoll instance
    
    Returns:
        Dict with poll results
    """
    from live.models import PollOption
    
    options = PollOption.objects.filter(poll=poll).order_by('order')
    total_votes = poll.total_votes()
    
    results = {
        'question': poll.question,
        'status': poll.status,
        'total_votes': total_votes,
        'options': []
    }
    
    for option in options:
        results['options'].append({
            'id': option.id,
            'text': option.text,
            'votes': option.votes_count,
            'percentage': option.vote_percentage()
        })
    
    return results


def create_recording(session, video_url, title=None, **kwargs):
    """
    Create a recording for a live session.
    
    Args:
        session: LiveSession instance
        video_url: URL of the recorded video
        title: Optional custom title
        **kwargs: Additional recording parameters
    
    Returns:
        SessionRecording instance
    """
    from live.models import SessionRecording
    
    if not session.enable_recording:
        raise ValidationError("Recording was not enabled for this session")
    
    if not title:
        title = f"{session.title} - Recording"
    
    recording = SessionRecording.objects.create(
        session=session,
        title=title,
        video_url=video_url,
        **kwargs
    )
    
    return recording


def track_recording_view(recording, user, watch_duration_seconds=0, last_position_seconds=0):
    """
    Track user viewing a recording.
    
    Args:
        recording: SessionRecording instance
        user: User viewing
        watch_duration_seconds: Total watch time
        last_position_seconds: Current playback position
    
    Returns:
        RecordingView instance
    """
    from live.models import RecordingView
    
    # Check access
    if recording.requires_enrollment:
        from enrollments.models import Enrollment
        if not Enrollment.objects.filter(
            user=user,
            course=recording.session.course,
            status='active'
        ).exists():
            raise PermissionDenied("You must be enrolled to view this recording")
    
    # Get or create view record
    view, created = RecordingView.objects.get_or_create(
        recording=recording,
        user=user
    )
    
    # Update watch stats
    view.watch_duration_seconds = max(view.watch_duration_seconds, watch_duration_seconds)
    view.last_position_seconds = last_position_seconds
    
    # Check if completed (watched 90%+)
    if recording.duration_seconds > 0:
        watch_percentage = (watch_duration_seconds / recording.duration_seconds) * 100
        if watch_percentage >= 90:
            view.completed = True
    
    view.save()
    
    # Update recording view count (first time only)
    if created:
        recording.views_count = F('views_count') + 1
        recording.save(update_fields=['views_count'])
    
    return view


def process_session_attendance(session):
    """
    Process attendance for all participants after session ends.
    
    Args:
        session: LiveSession instance
    
    Returns:
        Number of attendance records created
    """
    from live.models import SessionParticipant, SessionAttendance
    
    participants = SessionParticipant.objects.filter(session=session)
    count = 0
    
    for participant in participants:
        # Calculate attendance percentage
        attendance_rate = participant.attendance_rate()
        
        # Mark present if attended at least 75%
        marked_present = attendance_rate >= 75
        
        SessionAttendance.objects.update_or_create(
            session=session,
            participant=participant,
            defaults={
                'marked_present': marked_present,
                'attendance_percentage': attendance_rate
            }
        )
        count += 1
    
    return count


def get_session_analytics(session):
    """
    Get comprehensive analytics for a live session.
    
    Args:
        session: LiveSession instance
    
    Returns:
        Dict with session analytics
    """
    from live.models import (
        SessionParticipant, LiveChatMessage, LiveQuestion,
        LivePoll, SessionAttendance
    )
    
    participants = SessionParticipant.objects.filter(session=session)
    
    analytics = {
        'session': {
            'title': session.title,
            'status': session.status,
            'scheduled_duration': session.duration_minutes(),
            'actual_duration': session.actual_duration_minutes(),
        },
        'participation': {
            'total_registered': participants.count(),
            'total_joined': participants.filter(status__in=['joined', 'left']).count(),
            'currently_active': participants.filter(status='joined').count(),
            'attendance_rate': 0,
        },
        'engagement': {
            'total_messages': LiveChatMessage.objects.filter(session=session).count(),
            'total_questions': LiveQuestion.objects.filter(session=session).count(),
            'answered_questions': LiveQuestion.objects.filter(
                session=session,
                status='answered'
            ).count(),
            'total_polls': LivePoll.objects.filter(session=session).count(),
            'total_poll_votes': 0,
        },
        'recordings': {
            'count': session.recordings.count(),
            'total_views': session.recordings.aggregate(
                total=Sum('views_count')
            )['total'] or 0,
        }
    }
    
    # Calculate attendance rate
    attendance = SessionAttendance.objects.filter(session=session)
    if attendance.exists():
        analytics['participation']['attendance_rate'] = attendance.filter(
            marked_present=True
        ).count() / attendance.count() * 100
    
    # Calculate poll votes
    polls = LivePoll.objects.filter(session=session)
    analytics['engagement']['total_poll_votes'] = sum(p.total_votes() for p in polls)
    
    return analytics


def get_upcoming_sessions(user, limit=10):
    """
    Get upcoming live sessions for a user's enrolled courses.
    
    Args:
        user: User instance
        limit: Maximum number of sessions to return
    
    Returns:
        QuerySet of LiveSession instances
    """
    from live.models import LiveSession
    from enrollments.models import Enrollment
    
    # Get user's enrolled courses
    enrolled_courses = Enrollment.objects.filter(
        user=user,
        status='active'
    ).values_list('course_id', flat=True)
    
    sessions = LiveSession.objects.filter(
        course_id__in=enrolled_courses,
        status='scheduled',
        scheduled_start__gt=timezone.now()
    ).select_related('course', 'instructor').order_by('scheduled_start')[:limit]
    
    return sessions


def get_user_session_history(user, limit=20):
    """
    Get user's live session participation history.
    
    Args:
        user: User instance
        limit: Maximum number of sessions to return
    
    Returns:
        QuerySet of SessionParticipant instances
    """
    from live.models import SessionParticipant
    
    history = SessionParticipant.objects.filter(
        user=user
    ).select_related('session', 'session__course').order_by('-registered_at')[:limit]
    
    return history
