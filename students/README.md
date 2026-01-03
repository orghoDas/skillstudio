# Students App Documentation

## Overview
The students app manages student profiles, learning preferences, notes, bookmarks, achievements, and personalized dashboard for the SkillStudio platform. It provides comprehensive tools for students to track their learning journey and organize their study materials.

## Features
- **Student Profiles**: Extended profiles with learning preferences and goals
- **Learning Dashboard**: Personalized dashboard with progress tracking
- **Study Notes**: Create and manage notes on lessons and courses
- **Bookmarks**: Bookmark important lessons for quick access
- **Learning Streak**: Track consecutive days of learning activity
- **Achievements**: Earn achievements based on learning milestones
- **Activity Feed**: Timeline of recent learning activities
- **Weekly Progress**: Visual representation of weekly learning patterns
- **Statistics**: Comprehensive learning statistics and metrics

## Models

### StudentProfile
Extended profile information specific to students.

**Fields:**
- `id` (UUIDField, primary key) - Unique identifier
- `user` (OneToOneField to User) - Associated user account
- `preferred_learning_style` (CharField) - Learning style preference
  - Choices: 'visual', 'auditory', 'reading', 'kinesthetic'
- `learning_goals` (TextField) - Student's learning objectives
- `interests` (JSONField) - List of interest tags/topics
- `weekly_study_hours` (IntegerField) - Target study hours per week
- `preferred_study_time` (CharField) - Preferred time of day
  - Choices: 'morning', 'afternoon', 'evening', 'night'
- `total_courses_enrolled` (IntegerField) - Number of enrolled courses (denormalized)
- `total_courses_completed` (IntegerField) - Number of completed courses (denormalized)
- `total_certificates_earned` (IntegerField) - Number of certificates (denormalized)
- `total_watch_time` (IntegerField) - Total watch time in seconds (denormalized)
- `created_at`, `updated_at` (DateTimeField) - Timestamps

**Methods:**
- `update_statistics()` - Update denormalized statistics
- `calculate_completion_rate()` - Calculate course completion rate
- `get_learning_level()` - Determine student level (Beginner/Intermediate/Advanced)
- `__str__()` - String representation

**Indexes:**
- user field
- created_at (descending)

### StudentNote
Notes created by students on specific lessons.

**Fields:**
- `id` (UUIDField, primary key) - Unique identifier
- `student` (ForeignKey to User) - Student who created the note
- `lesson` (ForeignKey to Lesson) - Lesson the note is about
- `content` (TextField) - Note content
- `timestamp` (IntegerField, optional) - Video timestamp for the note (in seconds)
- `is_pinned` (BooleanField) - Whether note is pinned to top
- `tags` (JSONField) - List of custom tags
- `created_at`, `updated_at` (DateTimeField) - Timestamps

**Methods:**
- `pin()` - Pin note to top
- `unpin()` - Unpin note
- `add_tag(tag)` - Add a tag
- `remove_tag(tag)` - Remove a tag
- `__str__()` - String representation

**Indexes:**
- student field
- lesson field
- created_at (descending)
- is_pinned

### StudentBookmark
Bookmarks for quick access to important lessons.

**Fields:**
- `id` (UUIDField, primary key) - Unique identifier
- `student` (ForeignKey to User) - Student who created the bookmark
- `lesson` (ForeignKey to Lesson) - Bookmarked lesson
- `notes` (TextField, optional) - Optional notes about why bookmarked
- `created_at` (DateTimeField) - Timestamp

**Methods:**
- `__str__()` - String representation

**Constraints:**
- Unique constraint on (student, lesson) - one bookmark per student per lesson

**Indexes:**
- student field
- lesson field
- created_at (descending)

## Services

### get_or_create_student_profile(user)
Gets or creates a student profile for a user.

**Args:**
- `user` - User instance

**Returns:**
- StudentProfile instance

### update_student_profile(user, **kwargs)
Updates student profile with provided data.

**Args:**
- `user` - User instance
- `**kwargs` - Fields to update (learning_goals, interests, etc.)

**Returns:**
- Updated StudentProfile instance

**Raises:**
- `ValidationError` - If validation fails

### get_student_dashboard_data(user)
Gets comprehensive dashboard data for student.

**Args:**
- `user` - User instance

**Returns:**
- Dict containing:
  - enrolled_courses: List of active enrollments with progress
  - completed_courses: List of completed courses
  - in_progress_courses: Courses with partial completion
  - recommended_next_lessons: Suggested next lessons
  - total_certificates: Certificate count
  - completion_rate: Overall completion percentage

### get_student_activity_feed(user, limit=10)
Gets recent learning activities for student.

**Args:**
- `user` - User instance
- `limit` - Maximum number of activities to return

**Returns:**
- List of activity dicts:
  - type: 'enrollment', 'completion', 'certificate', 'review', 'note'
  - title: Activity title
  - description: Activity description
  - timestamp: When activity occurred
  - metadata: Additional activity data

### get_learning_streak(user)
Calculates current learning streak (consecutive days).

**Args:**
- `user` - User instance

**Returns:**
- Dict containing:
  - current_streak: Number of consecutive days
  - longest_streak: Historical longest streak
  - last_activity_date: Date of last learning activity
  - is_active_today: Whether user has learned today

**Algorithm:**
1. Gets all lesson progress records ordered by date
2. Counts consecutive days with activity
3. Tracks longest historical streak
4. Checks if streak is still active

### get_weekly_learning_progress(user)
Gets learning progress for the past 7 days.

**Args:**
- `user` - User instance

**Returns:**
- List of 7 dicts (one per day):
  - date: Date
  - lessons_completed: Number of lessons completed
  - time_spent: Minutes spent learning
  - courses_active: Number of courses accessed

### get_student_achievements(user, streak_data=None)
Calculates earned achievements based on milestones.

**Args:**
- `user` - User instance
- `streak_data` - Optional pre-calculated streak data

**Returns:**
- List of achievement dicts:
  - id: Achievement identifier
  - title: Achievement title
  - description: Achievement description
  - icon: Icon identifier
  - earned: Whether student has earned it
  - progress: Progress towards achievement (0-100)
  - earned_at: When achievement was earned

**Achievement Types:**
- First Course: Complete first course
- Dedicated Learner: 7-day learning streak
- Committed Student: 30-day learning streak
- Course Collector: Enroll in 5+ courses
- Course Master: Complete 10+ courses
- Certificate Earner: Earn first certificate
- Certified Expert: Earn 5+ certificates
- Note Taker: Create 10+ notes
- Speed Learner: Complete course in < 7 days

### create_student_note(student, lesson, content, timestamp=None, tags=None)
Creates a new student note.

**Args:**
- `student` - User instance
- `lesson` - Lesson instance
- `content` - Note content
- `timestamp` - Optional video timestamp
- `tags` - Optional list of tags

**Returns:**
- StudentNote instance

**Raises:**
- `ValidationError` - If validation fails

### update_student_note(note_id, student, **kwargs)
Updates an existing note.

**Args:**
- `note_id` - Note UUID
- `student` - User instance (for permission check)
- `**kwargs` - Fields to update

**Returns:**
- Updated StudentNote instance

**Raises:**
- `PermissionDenied` - If student doesn't own the note

### delete_student_note(note_id, student)
Deletes a student note.

**Args:**
- `note_id` - Note UUID
- `student` - User instance (for permission check)

**Raises:**
- `PermissionDenied` - If student doesn't own the note

### create_bookmark(student, lesson, notes=None)
Creates a bookmark for a lesson.

**Args:**
- `student` - User instance
- `lesson` - Lesson instance
- `notes` - Optional notes about bookmark

**Returns:**
- StudentBookmark instance

**Raises:**
- `IntegrityError` - If bookmark already exists

### delete_bookmark(bookmark_id, student)
Deletes a bookmark.

**Args:**
- `bookmark_id` - Bookmark UUID
- `student` - User instance (for permission check)

**Raises:**
- `PermissionDenied` - If student doesn't own the bookmark

### get_student_notes(student, lesson=None, course=None)
Gets student's notes, optionally filtered.

**Args:**
- `student` - User instance
- `lesson` - Optional lesson filter
- `course` - Optional course filter

**Returns:**
- QuerySet of StudentNote objects

### get_student_bookmarks(student, course=None)
Gets student's bookmarks, optionally filtered.

**Args:**
- `student` - User instance
- `course` - Optional course filter

**Returns:**
- QuerySet of StudentBookmark objects

## API Endpoints

### Student Dashboard
```http
GET /api/students/dashboard/
```
Get comprehensive student dashboard data.

**Permissions:** IsAuthenticated, IsStudent

**Response:**
```json
{
  "streak": {
    "current_streak": 7,
    "longest_streak": 14,
    "last_activity_date": "2024-01-15",
    "is_active_today": true
  },
  "weekly_progress": [
    {
      "date": "2024-01-15",
      "lessons_completed": 5,
      "time_spent": 120,
      "courses_active": 2
    }
  ],
  "achievements": [
    {
      "id": "first_course",
      "title": "First Course",
      "earned": true,
      "progress": 100,
      "earned_at": "2024-01-10T10:00:00Z"
    }
  ],
  "courses": [
    {
      "id": 1,
      "title": "Course Title",
      "progress": 45,
      "next_lesson": {
        "id": 5,
        "title": "Lesson 5"
      }
    }
  ],
  "activity_feed": [
    {
      "type": "completion",
      "title": "Completed Lesson 4",
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Activity Feed
```http
GET /api/students/activity-feed/
```
Get recent learning activities.

**Permissions:** IsAuthenticated, IsStudent

**Response:**
```json
[
  {
    "type": "enrollment",
    "title": "Enrolled in Advanced Python",
    "description": "Started learning Advanced Python",
    "timestamp": "2024-01-15T10:00:00Z",
    "metadata": {
      "course_id": 1,
      "course_title": "Advanced Python"
    }
  }
]
```

### Student Profile
```http
GET /api/students/profile/
PUT /api/students/profile/
```
Get or update student profile.

**Permissions:** IsAuthenticated, IsStudent

**Request Body (PUT):**
```json
{
  "preferred_learning_style": "visual",
  "learning_goals": "Master web development",
  "interests": ["Python", "Django", "React"],
  "weekly_study_hours": 10,
  "preferred_study_time": "evening"
}
```

**Response:**
```json
{
  "id": "uuid",
  "user": {
    "id": 1,
    "email": "student@example.com"
  },
  "preferred_learning_style": "visual",
  "learning_goals": "Master web development",
  "interests": ["Python", "Django", "React"],
  "weekly_study_hours": 10,
  "total_courses_enrolled": 5,
  "total_courses_completed": 2,
  "total_certificates_earned": 2
}
```

### Notes Management

#### List/Create Notes
```http
GET /api/students/notes/
POST /api/students/notes/
```

**Query Parameters (GET):**
- `lesson` - Filter by lesson ID
- `course` - Filter by course ID

**Request Body (POST):**
```json
{
  "lesson": 1,
  "content": "Important concept: Django ORM...",
  "timestamp": 120,
  "tags": ["django", "orm"]
}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "lesson": {
      "id": 1,
      "title": "Lesson Title",
      "course": "Course Title"
    },
    "content": "Important concept...",
    "timestamp": 120,
    "is_pinned": false,
    "tags": ["django", "orm"],
    "created_at": "2024-01-15T10:00:00Z"
  }
]
```

#### Update/Delete Note
```http
GET /api/students/notes/{id}/
PUT /api/students/notes/{id}/
PATCH /api/students/notes/{id}/
DELETE /api/students/notes/{id}/
```

**Request Body (PUT/PATCH):**
```json
{
  "content": "Updated note content",
  "is_pinned": true,
  "tags": ["django", "orm", "important"]
}
```

### Bookmarks Management

#### List/Create Bookmarks
```http
GET /api/students/bookmarks/
POST /api/students/bookmarks/
```

**Query Parameters (GET):**
- `course` - Filter by course ID

**Request Body (POST):**
```json
{
  "lesson": 1,
  "notes": "Come back to this lesson"
}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "lesson": {
      "id": 1,
      "title": "Lesson Title",
      "course": "Course Title"
    },
    "notes": "Come back to this lesson",
    "created_at": "2024-01-15T10:00:00Z"
  }
]
```

#### Delete Bookmark
```http
DELETE /api/students/bookmarks/{id}/
```

**Response:**
```json
{
  "message": "Bookmark deleted successfully"
}
```

## Integration Points

### Accounts App
- Uses User model with student role
- Profile extends base user profile
- Permissions: IsStudent

### Courses App
- Accesses lesson information
- Retrieves course details
- Links notes/bookmarks to lessons

### Enrollments App
- Progress tracking
- Completion status
- Last activity timestamps
- Resume lesson functionality

### Certificates App
- Certificate count
- Achievement tracking
- Milestone verification

### Social App
- Review activities in feed
- Learning circle participation
- Community engagement

### Analytics App
- Learning patterns
- Time spent tracking
- Progress analytics

## Testing

The students app includes 28 comprehensive tests (largest test suite in the project):

### Model Tests (8 tests)
- StudentProfile creation and updates
- StudentNote CRUD operations
- StudentBookmark creation and constraints
- Statistics calculation
- Learning level determination

### Service Tests (12 tests)
- Profile management
- Dashboard data generation
- Activity feed generation
- Learning streak calculation
- Weekly progress tracking
- Achievement system
- Notes CRUD
- Bookmarks CRUD
- Filtering and querying

### API Tests (8 tests)
- Dashboard endpoint
- Profile CRUD operations
- Notes list/create/update/delete
- Bookmarks list/create/delete
- Activity feed
- Permission checks

Run tests:
```bash
python manage.py test students
```

Run with verbose output:
```bash
python manage.py test students -v 2
```

## Usage Examples

### Creating Student Profile
```python
from students.services import get_or_create_student_profile, update_student_profile
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='student@example.com')

# Create profile
profile = get_or_create_student_profile(user)

# Update profile
updated_profile = update_student_profile(
    user,
    preferred_learning_style='visual',
    learning_goals='Master Python and Django',
    interests=['Python', 'Django', 'Web Development'],
    weekly_study_hours=10
)
```

### Managing Notes
```python
from students.services import create_student_note, update_student_note
from courses.models import Lesson

lesson = Lesson.objects.get(id=1)

# Create note
note = create_student_note(
    student=user,
    lesson=lesson,
    content='Important concept about Django models',
    timestamp=120,  # 2 minutes into video
    tags=['django', 'models']
)

# Update note
updated_note = update_student_note(
    note_id=note.id,
    student=user,
    content='Updated note content',
    is_pinned=True
)
```

### Managing Bookmarks
```python
from students.services import create_bookmark, get_student_bookmarks

# Create bookmark
bookmark = create_bookmark(
    student=user,
    lesson=lesson,
    notes='Review this later'
)

# Get all bookmarks for a course
bookmarks = get_student_bookmarks(user, course=course)
```

### Tracking Learning Streak
```python
from students.services import get_learning_streak, get_weekly_learning_progress

# Get current streak
streak = get_learning_streak(user)
print(f"Current streak: {streak['current_streak']} days")
print(f"Longest streak: {streak['longest_streak']} days")

# Get weekly progress
weekly = get_weekly_learning_progress(user)
for day in weekly:
    print(f"{day['date']}: {day['lessons_completed']} lessons")
```

### Getting Achievements
```python
from students.services import get_student_achievements

achievements = get_student_achievements(user)
for achievement in achievements:
    if achievement['earned']:
        print(f"✓ {achievement['title']}")
    else:
        print(f"  {achievement['title']} ({achievement['progress']}%)")
```

## Learning Streak Algorithm

The learning streak tracks consecutive days of learning activity:

1. **Activity Detection**: Any lesson progress counts as activity
2. **Streak Calculation**:
   - Start from today, work backwards
   - Count consecutive days with activity
   - Break on first day without activity (allowing 1-day gap on weekends)
3. **Longest Streak**: Historical maximum maintained separately
4. **Active Status**: Streak is "active" if activity occurred today

Weekend grace period: 1 day gap allowed if both days are weekend days.

## Achievement System

Achievements are calculated dynamically based on student metrics:

| Achievement | Requirement | Icon |
|------------|-------------|------|
| First Course | Complete 1 course | 🎓 |
| Dedicated Learner | 7-day streak | 🔥 |
| Committed Student | 30-day streak | 💎 |
| Course Collector | Enroll in 5 courses | 📚 |
| Course Master | Complete 10 courses | 👑 |
| Certificate Earner | Earn 1 certificate | 📜 |
| Certified Expert | Earn 5 certificates | 🏆 |
| Note Taker | Create 10 notes | 📝 |
| Speed Learner | Complete course < 7 days | ⚡ |

Progress is shown as percentage for partially completed achievements.

## Performance Considerations

- **Denormalized Statistics**: Key metrics cached in StudentProfile
- **Efficient Queries**: Use select_related for notes/bookmarks with lessons
- **Indexed Fields**: user, lesson, created_at for fast lookups
- **Streak Caching**: Calculate once, cache for dashboard
- **Activity Feed Limits**: Default 10 items, pagination for more
- **Database-level Aggregations**: Count and sum operations at DB level

## Security

- **Permission Checks**: IsStudent permission on all endpoints
- **Ownership Validation**: Students can only access their own data
- **Note/Bookmark Privacy**: No public access to personal notes
- **Profile Privacy**: Profile only accessible to owner
- **Lesson Access**: Validates enrollment before allowing notes/bookmarks

## Future Enhancements

1. **Study Groups**: Collaborative study sessions
2. **Flashcards**: Create flashcards from notes
3. **Spaced Repetition**: Intelligent review reminders
4. **Note Sharing**: Share notes with other students (opt-in)
5. **Voice Notes**: Audio notes on lessons
6. **Advanced Achievements**: More complex achievement criteria
7. **Learning Analytics**: Personalized insights and recommendations
8. **Study Timer**: Pomodoro timer integration
9. **Goal Tracking**: Track progress towards learning goals
10. **Peer Comparison**: Anonymous benchmarking against peers
