# Live Streaming Module

The Live Streaming module provides comprehensive real-time video streaming capabilities for courses, including live classes, workshops, webinars, interactive chat, Q&A sessions, polls, and recording management.

## Features

### Core Features
- **Live Sessions**: Schedule and conduct live classes, workshops, webinars, and Q&A sessions
- **Real-Time Chat**: Interactive chat during live sessions with emoji support and replies
- **Q&A System**: Question submission, upvoting, and instructor answers
- **Interactive Polls**: Create and conduct polls with real-time results
- **Session Recording**: Automatic recording with progress tracking
- **Attendance Tracking**: Automated attendance calculation based on participation
- **Multiple Platforms**: Support for Agora, Zoom, Google Meet, Microsoft Teams

### Advanced Features
- **Participant Management**: Track join/leave times, engagement metrics
- **Engagement Analytics**: Chat messages, questions asked, poll participation
- **Watch Progress**: Track recording viewing with completion detection
- **Session Analytics**: Comprehensive metrics on participation and engagement
- **Access Control**: Enrollment-based access, password protection, capacity limits

---

## Models

### 1. LiveSession
Main model for live streaming sessions.

**Key Fields:**
- `course`: ForeignKey to Course
- `instructor`: Session host
- `title`, `description`: Session information
- `session_type`: class, workshop, webinar, qa, office_hours
- `scheduled_start`, `scheduled_end`: Session timing
- `actual_start`, `actual_end`: Actual session duration
- `platform`: agora, zoom, meet, teams, custom
- `meeting_link`, `meeting_id`, `meeting_password`: Access credentials
- `stream_key`, `channel_name`: Streaming credentials
- `max_participants`: Capacity limit
- `enable_chat`, `enable_qa`, `enable_polls`, `enable_recording`: Feature flags
- `status`: scheduled, live, ended, cancelled

**Methods:**
- `is_upcoming()`: Check if session is upcoming
- `is_live()`: Check if session is currently live
- `is_past()`: Check if session has ended
- `duration_minutes()`: Get scheduled duration
- `participant_count()`: Get number of participants
- `available_slots()`: Get remaining capacity

### 2. SessionParticipant
Tracks user participation in sessions.

**Key Fields:**
- `session`: ForeignKey to LiveSession
- `user`: Participant user
- `status`: registered, joined, left, banned
- `joined_at`, `left_at`: Participation timing
- `duration_seconds`: Total watch time
- `chat_messages_count`, `questions_asked`, `polls_answered`: Engagement metrics
- `can_unmute`, `can_share_screen`, `is_moderator`: Permissions

**Methods:**
- `attendance_rate()`: Calculate attendance percentage

### 3. LiveChatMessage
Real-time chat messages during sessions.

**Key Fields:**
- `session`: ForeignKey to LiveSession
- `user`: Message sender
- `content`: Message text
- `message_type`: text, emoji, file, system
- `is_pinned`, `is_deleted`, `is_edited`: Message flags
- `reply_to`: ForeignKey to self (for threaded replies)
- `likes_count`: Reaction count

### 4. LiveQuestion
Q&A questions during sessions.

**Key Fields:**
- `session`: ForeignKey to LiveSession
- `user`: Question asker
- `question`, `answer`: Question and answer text
- `status`: pending, answered, dismissed
- `is_anonymous`: Anonymous posting flag
- `upvotes`: Vote count for prioritization
- `is_featured`: Featured question flag
- `answered_by`, `answered_at`: Response tracking

### 5. LivePoll
Interactive polls during sessions.

**Key Fields:**
- `session`: ForeignKey to LiveSession
- `created_by`: Poll creator (instructor)
- `question`, `description`: Poll details
- `status`: draft, active, closed
- `allow_multiple_answers`: Multiple choice flag
- `show_results_immediately`: Visibility setting
- `is_anonymous`: Anonymous voting flag
- `duration_seconds`: Poll duration
- `started_at`, `ends_at`: Poll timing

**Methods:**
- `total_votes()`: Get total vote count
- `is_active()`: Check if poll is active

### 6. PollOption
Poll answer options.

**Key Fields:**
- `poll`: ForeignKey to LivePoll
- `text`: Option text
- `order`: Display order
- `votes_count`: Denormalized vote count

**Methods:**
- `vote_percentage()`: Calculate percentage of total votes

### 7. PollVote
User votes on poll options.

**Key Fields:**
- `poll`: ForeignKey to LivePoll
- `option`: ForeignKey to PollOption
- `user`: Voter

### 8. SessionRecording
Recordings of live sessions.

**Key Fields:**
- `session`: ForeignKey to LiveSession
- `title`, `description`: Recording information
- `video_url`, `thumbnail_url`: Media URLs
- `duration_seconds`, `file_size_mb`: File details
- `processing_status`: pending, processing, ready, failed
- `is_public`, `requires_enrollment`: Access control
- `views_count`, `downloads_count`: Analytics

**Methods:**
- `duration_formatted()`: Get HH:MM:SS format

### 9. RecordingView
Tracks recording views and watch progress.

**Key Fields:**
- `recording`: ForeignKey to SessionRecording
- `user`: Viewer
- `watch_duration_seconds`: Total watch time
- `last_position_seconds`: Current position
- `completed`: Completion flag (90%+ watched)
- `device_type`, `browser`: Device information

**Methods:**
- `watch_percentage()`: Calculate watch percentage

### 10. SessionAttendance
Attendance records for certification.

**Key Fields:**
- `session`: ForeignKey to LiveSession
- `participant`: ForeignKey to SessionParticipant
- `marked_present`: Attendance flag
- `attendance_percentage`: Calculated percentage
- `verified_by`, `verified_at`: Manual verification
- `notes`: Additional notes

---

## API Endpoints

### Session Management
- `GET /api/live/sessions/` - List all sessions
  - Query params: `course`, `status`, `instructor`
- `POST /api/live/sessions/create/` - Create session (instructor only)
- `GET /api/live/sessions/{id}/` - Get session details
- `PUT /api/live/sessions/{id}/` - Update session (instructor only)
- `DELETE /api/live/sessions/{id}/` - Delete session (instructor only)
- `POST /api/live/sessions/{id}/start/` - Start session (instructor only)
- `POST /api/live/sessions/{id}/end/` - End session (instructor only)

### Participation
- `POST /api/live/sessions/{id}/join/` - Join session
- `POST /api/live/sessions/{id}/leave/` - Leave session
- `GET /api/live/sessions/{id}/participants/` - List participants

### Chat
- `GET /api/live/sessions/{id}/chat/` - Get chat messages
  - Query params: `limit` (default: 100)
- `POST /api/live/sessions/{id}/chat/send/` - Send message
  - Body: `{content, message_type, reply_to, file_url}`

### Q&A
- `GET /api/live/sessions/{id}/questions/` - List questions
  - Query params: `status`
- `POST /api/live/sessions/{id}/questions/ask/` - Ask question
  - Body: `{question, is_anonymous}`
- `POST /api/live/questions/{id}/answer/` - Answer question (instructor only)
  - Body: `{answer}`
- `POST /api/live/questions/{id}/upvote/` - Upvote question

### Polls
- `GET /api/live/sessions/{id}/polls/` - List polls
- `POST /api/live/sessions/{id}/polls/create/` - Create poll (instructor only)
  - Body: `{question, options[], allow_multiple_answers, show_results_immediately, is_anonymous, duration_seconds}`
- `POST /api/live/polls/{id}/start/` - Start poll (instructor only)
  - Body: `{duration_seconds}` (optional)
- `POST /api/live/polls/{id}/close/` - Close poll (instructor only)
- `POST /api/live/polls/{id}/vote/` - Vote on poll
  - Body: `{option_ids[]}`
- `GET /api/live/polls/{id}/results/` - Get poll results

### Recordings
- `GET /api/live/sessions/{id}/recordings/` - List session recordings
- `POST /api/live/sessions/{id}/recordings/create/` - Create recording (instructor only)
  - Body: `{video_url, title, description, thumbnail_url, duration_seconds, file_size_mb, is_public, requires_enrollment}`
- `GET /api/live/recordings/{id}/` - Get recording details
- `POST /api/live/recordings/{id}/track/` - Track viewing progress
  - Body: `{watch_duration_seconds, last_position_seconds, device_type, browser}`

### Attendance & Analytics
- `GET /api/live/sessions/{id}/attendance/` - Get attendance (instructor only)
- `GET /api/live/sessions/{id}/analytics/` - Get session analytics (instructor only)

### User-Specific
- `GET /api/live/upcoming/` - Get upcoming sessions for enrolled courses
- `GET /api/live/history/` - Get user's session participation history

---

## Usage Examples

### Creating a Live Session

```python
from live import services
from datetime import timedelta
from django.utils import timezone

session = services.create_live_session(
    course=course,
    instructor=instructor_user,
    title="Introduction to Django",
    scheduled_start=timezone.now() + timedelta(hours=1),
    scheduled_end=timezone.now() + timedelta(hours=2),
    description="Learn Django basics",
    session_type='class',
    platform='agora',
    enable_chat=True,
    enable_qa=True,
    enable_polls=True,
    max_participants=50
)
```

### Starting and Ending a Session

```python
# Start session
started_session = services.start_live_session(session, instructor_user)

# End session
ended_session = services.end_live_session(session, instructor_user)
# Automatically marks all participants as left and processes attendance
```

### Joining a Session

```python
# Student joins session
participant = services.join_session(session, student_user)

# Leave session
participant = services.leave_session(session, student_user)
# Automatically calculates duration
```

### Sending Chat Messages

```python
message = services.send_chat_message(
    session=session,
    user=student_user,
    content="Great explanation!",
    message_type='text'
)

# Reply to a message
reply = services.send_chat_message(
    session=session,
    user=student_user,
    content="Thanks for asking that!",
    reply_to=message
)
```

### Q&A Workflow

```python
# Student asks question
question = services.ask_question(
    session=session,
    user=student_user,
    question="What is the difference between lists and tuples?",
    is_anonymous=False
)

# Other students upvote
services.upvote_question(question, another_user)

# Instructor answers
services.answer_question(
    question=question,
    user=instructor_user,
    answer="Lists are mutable, tuples are immutable..."
)
```

### Creating and Running Polls

```python
# Create poll
poll = services.create_poll(
    session=session,
    user=instructor_user,
    question="What topic should we cover next?",
    options=["Django ORM", "Django REST", "Testing", "Deployment"],
    allow_multiple_answers=False,
    show_results_immediately=True,
    duration_seconds=60
)

# Start poll
services.start_poll(poll, instructor_user, duration_seconds=60)

# Students vote
services.vote_poll(
    poll=poll,
    user=student_user,
    option_ids=[option1.id]
)

# Get results
results = services.get_poll_results(poll)
# {
#     'question': '...',
#     'status': 'active',
#     'total_votes': 15,
#     'options': [
#         {'id': 1, 'text': 'Django ORM', 'votes': 8, 'percentage': 53.3},
#         ...
#     ]
# }

# Close poll
services.close_poll(poll, instructor_user)
```

### Recording Management

```python
# Create recording
recording = services.create_recording(
    session=session,
    video_url="https://cdn.example.com/recording.mp4",
    title="Introduction to Django - Recording",
    duration_seconds=3600,
    file_size_mb=250.5,
    requires_enrollment=True
)

# Track viewing
view = services.track_recording_view(
    recording=recording,
    user=student_user,
    watch_duration_seconds=1800,  # 30 minutes
    last_position_seconds=1800
)
# Automatically marks as completed if 90%+ watched
```

### Session Analytics

```python
analytics = services.get_session_analytics(session)
# {
#     'session': {
#         'title': '...',
#         'status': 'ended',
#         'scheduled_duration': 60,
#         'actual_duration': 65
#     },
#     'participation': {
#         'total_registered': 45,
#         'total_joined': 38,
#         'currently_active': 0,
#         'attendance_rate': 84.4
#     },
#     'engagement': {
#         'total_messages': 234,
#         'total_questions': 18,
#         'answered_questions': 15,
#         'total_polls': 3,
#         'total_poll_votes': 112
#     },
#     'recordings': {
#         'count': 1,
#         'total_views': 156
#     }
# }
```

---

## Business Logic

### Attendance Calculation

Attendance is automatically calculated when a session ends:

```python
attendance_percentage = (participant_duration_seconds / 60) / session_actual_duration_minutes * 100
marked_present = attendance_percentage >= 75
```

A participant is marked present if they attended at least 75% of the session.

### Poll Vote Percentage

```python
percentage = (option_votes / total_poll_votes) * 100
```

### Recording Completion

A recording is marked as completed when the user has watched 90% or more:

```python
watch_percentage = (watch_duration_seconds / recording_duration_seconds) * 100
completed = watch_percentage >= 90
```

### Session Status Flow

1. **Scheduled**: Created but not started
2. **Live**: Session is currently active
3. **Ended**: Session has finished
4. **Cancelled**: Session was cancelled

---

## Integration Points

### With Courses Module
- Sessions are linked to courses
- Enrollment requirement checking
- Instructor validation

### With Enrollments Module
- Check enrollment before joining
- Track course-specific session history

### With Certificates Module
- Attendance records for certification
- Session completion tracking

---

## Database Indexes

The module includes optimized indexes for:
- Session queries by course and status
- Participant lookups by session and user
- Chat message pagination by session
- Question sorting by upvotes
- Poll result calculations
- Recording view tracking

---

## Testing

Run the test suite:

```bash
python manage.py test live
```

Test coverage includes:
- Model creation and validation
- Service function logic
- API endpoint authorization
- Attendance calculation
- Poll voting and results
- Recording view tracking

---

## Django Admin

All models are registered in Django Admin with:
- **Color-coded status badges** (scheduled/live/ended)
- **Engagement metrics** (chat/questions/polls)
- **Attendance visualization** with percentage bars
- **Poll results** with visual bars
- **Watch progress** tracking
- **Search and filtering** by session, user, status

---

## Permissions

- **Public**: Browse published sessions
- **Authenticated**: Join sessions, participate in chat/Q&A
- **Enrolled Students**: Access course sessions, view recordings
- **Instructors**: Create/manage sessions, start/end sessions, create polls, answer questions
- **Session Moderators**: Additional chat moderation permissions

---

## Best Practices

### Session Scheduling
- Schedule sessions at least 1 hour in advance
- Check for instructor availability (no overlapping sessions)
- Send reminders 24 hours before

### Capacity Management
- Set appropriate max_participants limits
- Monitor available_slots before session starts
- Consider platform limitations

### Recording Storage
- Use CDN for video delivery
- Generate thumbnails for better UX
- Set appropriate access controls

### Engagement
- Enable chat for interactive sessions
- Use polls for audience feedback
- Feature important questions in Q&A

### Analytics
- Track engagement metrics per session
- Monitor attendance rates
- Analyze poll results for content improvement

---

## Future Enhancements

Potential improvements:
- WebSocket support for real-time updates
- Breakout rooms for group discussions
- Screen sharing and whiteboard features
- Live transcription and captions
- Automatic highlight generation from recordings
- AI-based question suggestions
- Multi-language support for chat
- Session templates for recurring events
- Integration with calendar services
- Advanced analytics dashboard

---

## Dependencies

- Django 6.0+
- Django REST Framework 3.16+
- PostgreSQL (for complex queries)
- Celery (for scheduled reminders - optional)
- Streaming platform SDK (Agora/Zoom/etc.)

---

## Migration

Create and apply migrations:

```bash
python manage.py makemigrations live
python manage.py migrate live
```

The module includes comprehensive migrations for all 10 models with proper indexes and constraints.
