# Events App

The Events app provides a comprehensive event management system for the SkillStudio platform, enabling users to create, register for, and manage various types of educational events.

## Features

### Event Types
- **Workshops**: Hands-on learning sessions
- **Webinars**: Online seminars and presentations
- **Live Sessions**: Interactive live teaching sessions
- **Guest Lectures**: Special talks by guest speakers
- **Study Groups**: Collaborative learning sessions
- **Office Hours**: One-on-one support sessions

### Core Functionality

#### Event Management
- Create and publish events
- Set event capacity and pricing (paid/free)
- Schedule with start and end times
- Attach events to specific courses
- Event status workflow (draft → published → completed/cancelled)

#### Registration System
- Seat-based registration with capacity management
- Payment tracking for paid events
- Registration status (pending → confirmed → cancelled)
- Enrollment verification (must be enrolled in course)
- Duplicate registration prevention

#### Attendance Tracking
- Mark user attendance
- Track attendance timestamps
- Calculate attendance rates
- Generate attendance reports

#### Feedback & Reviews
- Submit event ratings (1-5 stars)
- Provide written feedback
- View aggregated ratings
- Require attendance for feedback

#### Resources
- Upload event materials (slides, recordings)
- Attach resources post-event
- Access control (only for registered users)

#### Analytics
- Total registrations count
- Attendance statistics
- Average ratings
- Cancellation rates
- Revenue tracking (for paid events)

## Models

### Event
Represents an event with scheduling, capacity, and pricing details.

**Key Fields:**
- `title`, `description`: Basic information
- `event_type`: Type of event (workshop, webinar, etc.)
- `start_time`, `end_time`: Scheduling
- `total_seats`, `price`: Capacity and pricing
- `status`: Current state (draft/published/cancelled/completed)
- `course`: Associated course (optional)
- `organizer`: Event creator

**Methods:**
- `available_seats()`: Calculate remaining capacity
- `is_full()`: Check if event is at capacity

### EventRegistration
Tracks user registrations for events.

**Key Fields:**
- `event`, `user`: Registration mapping
- `status`: Registration state
- `payment_status`: Payment tracking
- `attended`: Attendance flag

### EventFeedback
Stores user feedback and ratings.

**Key Fields:**
- `event`, `user`: Feedback mapping
- `rating`: 1-5 star rating
- `comment`: Written feedback

### EventAttendanceLog
Logs attendance records.

**Key Fields:**
- `event`, `user`: Attendance mapping
- `attended_at`: Timestamp
- `marked_by`: Who marked attendance

### EventResource
Stores event-related materials.

**Key Fields:**
- `event`: Associated event
- `title`, `description`: Resource information
- `file`: Uploaded file
- `uploaded_by`: Uploader

## API Endpoints

### Event Management
```
GET    /api/events/                          # List events (with filters)
POST   /api/events/                          # Create event
GET    /api/events/<id>/                     # Event details
PUT    /api/events/<id>/                     # Update event
DELETE /api/events/<id>/                     # Delete event
```

**Query Parameters:**
- `status`: Filter by status (draft/published/etc.)
- `event_type`: Filter by type
- `course_id`: Filter by course
- `upcoming`: Show only upcoming events

### Registration
```
POST   /api/events/<id>/register/            # Register for event
POST   /api/events/<id>/cancel/              # Cancel registration
GET    /api/events/registrations/my/         # My registrations
```

### Feedback
```
POST   /api/events/<id>/feedback/submit/     # Submit feedback
GET    /api/events/<id>/feedback/            # List feedback
```

### Analytics (Instructor/Staff)
```
GET    /api/events/<id>/analytics/           # Event analytics
GET    /api/events/<id>/registrations/       # Registration list
POST   /api/events/<id>/attendance/mark/     # Mark attendance
```

### Resources
```
POST   /api/events/<id>/resources/upload/    # Upload resource
GET    /api/events/<id>/resources/           # List resources
```

### Discovery
```
GET    /api/events/upcoming/                 # Upcoming events
GET    /api/events/featured/                 # Featured events
```

## Usage Examples

### Create an Event
```python
POST /api/events/
{
    "title": "Django Workshop",
    "description": "Learn Django basics",
    "event_type": "workshop",
    "course_id": 1,
    "start_time": "2024-02-01T10:00:00Z",
    "end_time": "2024-02-01T12:00:00Z",
    "total_seats": 30,
    "price": 50.00,
    "location": "Room 101"
}
```

### Register for Event
```python
POST /api/events/1/register/
# No body required - uses authenticated user
```

### Submit Feedback
```python
POST /api/events/1/feedback/submit/
{
    "rating": 5,
    "comment": "Excellent workshop! Very informative."
}
```

### View Analytics
```python
GET /api/events/1/analytics/

Response:
{
    "total_registrations": 25,
    "confirmed_count": 23,
    "attended_count": 20,
    "attendance_rate": "86.96",
    "average_rating": "4.50",
    "feedback_count": 18
}
```

## Permissions

- **Public**: List published events, view details
- **Authenticated**: Register, submit feedback, view own registrations
- **Instructor/Staff**: Create events, mark attendance, view analytics
- **Organizer**: Full control over their events

## Business Logic (services.py)

### Key Functions

#### `register_for_event(event, user)`
Handles event registration with validation:
- Checks course enrollment
- Validates capacity
- Prevents duplicate registrations
- Creates registration record

#### `cancel_event_registration(event, user)`
Cancels user registration:
- Updates status to 'cancelled'
- TODO: Handle refunds for paid events

#### `mark_attendance(event, user, marked_by)`
Records attendance:
- Creates attendance log
- Updates registration attended flag

#### `submit_event_feedback(event, user, rating, comment)`
Submits feedback with validation:
- Requires attendance
- Prevents duplicate feedback
- Validates rating range (1-5)

#### `get_event_analytics(event)`
Calculates event metrics:
- Registration statistics
- Attendance rates
- Rating averages

## Admin Interface

The Events admin provides:
- Event management with fieldsets
- Registration tracking
- Feedback moderation
- Attendance logs
- Resource management
- Inline editing for related objects

## Testing

Run tests:
```bash
python manage.py test events
```

Test coverage includes:
- Event creation and capacity management
- Registration workflow
- Attendance tracking
- Feedback submission
- Analytics calculations
- Permission checks

## Future Enhancements

- [ ] Email notifications (registration confirmations, reminders)
- [ ] Calendar integration (iCal export)
- [ ] Waitlist management for full events
- [ ] Refund processing for cancellations
- [ ] Recurring events
- [ ] Event templates
- [ ] Certificate generation for attendees
