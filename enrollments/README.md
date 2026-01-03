# Enrollments App Documentation

## Overview

The Enrollments app manages student enrollments, progress tracking, lesson completion, and wishlist functionality for the SkillStudio learning platform.

## Features

### 🎓 Enrollment Management
- Enroll in courses
- Cancel enrollments
- Reactivate canceled enrollments
- Track enrollment status (active, completed, canceled)
- View all enrollments (My Learning)
- View completed courses

### 📊 Progress Tracking
- Track lesson watch time
- Auto-complete lessons when threshold reached (80%)
- Manual lesson completion
- Track course completion percentage
- Resume lesson functionality
- Next lesson navigation
- Detailed progress statistics

### 📋 Wishlist
- Add courses to wishlist
- Remove courses from wishlist
- View wishlist
- Check if course is in wishlist

### 📈 Analytics & Statistics
- Overall enrollment statistics
- Learning progress dashboard
- Course-wise progress details
- Total watch time tracking
- Completion rates

### 👨‍🏫 Instructor Features
- Lesson analytics CSV export
- Student progress tracking
- Drop-off rate analysis

## Models

### Enrollment
Represents a user's enrollment in a course.

**Fields:**
- `user`: Student enrolled
- `course`: Course enrolled in
- `status`: 'active', 'completed', or 'canceled'
- `is_completed`: Boolean completion flag
- `enrolled_at`: Enrollment timestamp
- `completed_at`: Completion timestamp

**Constraints:**
- Unique together: (user, course)

### LessonProgress
Tracks progress for individual lessons.

**Fields:**
- `enrollment`: Related enrollment
- `user`: Student
- `lesson`: Lesson being tracked
- `watch_time`: Seconds watched
- `is_completed`: Boolean completion flag
- `started_at`: First access timestamp
- `completed_at`: Completion timestamp

**Constraints:**
- Unique together: (enrollment, lesson)

### Wishlist
Stores courses users want to learn.

**Fields:**
- `user`: Student
- `course`: Course on wishlist
- `added_at`: Addition timestamp

**Constraints:**
- Unique together: (user, course)

## API Endpoints

### Enrollment Management

#### List All Enrollments
```
GET /api/enrollments/my-enrollments/
```
Returns all enrollments for the authenticated user.

#### Get Enrollment Details
```
GET /api/enrollments/enrollments/<enrollment_id>/
```
Returns detailed information about a specific enrollment including progress.

#### Enroll in Course
```
POST /api/enrollments/enroll/
Body: {"course_id": 1}
```
Enrolls the user in a course. Creates new or reactivates canceled enrollment.

#### Cancel Enrollment
```
PATCH /api/enrollments/enrollments/<enrollment_id>/cancel/
```
Cancels an active enrollment.

#### My Learning
```
GET /api/enrollments/my-learning/
```
Returns all active enrollments.

#### Completed Courses
```
GET /api/enrollments/completed-courses/
```
Returns all completed courses.

### Progress Tracking

#### Get Course Progress
```
GET /api/enrollments/courses/<course_id>/progress/
```
Returns overall progress statistics for a course.

**Response:**
```json
{
  "course_id": 1,
  "course_title": "Python Fundamentals",
  "total_lessons": 20,
  "completed_lessons": 15,
  "progress_percentage": 75.0,
  "is_completed": false
}
```

#### Get Lesson Progress
```
GET /api/enrollments/lessons/<lesson_id>/progress/
```
Returns progress details for a specific lesson.

#### Update Watch Time
```
PATCH /api/enrollments/lessons/<lesson_id>/watch-time/
Body: {"watch_time": 450}
```
Updates the watch time for a lesson. Auto-completes if threshold reached.

#### Resume Lesson
```
GET /api/enrollments/courses/<course_id>/resume-lesson/
```
Returns the next incomplete lesson to continue learning.

#### Get Next Lesson
```
GET /api/enrollments/courses/<course_id>/lessons/<lesson_id>/next/
```
Returns the next lesson after the current one.

#### Complete Lesson
```
POST /api/enrollments/lessons/<lesson_id>/complete/
```
Manually marks a lesson as completed.

### Wishlist

#### List Wishlist
```
GET /api/enrollments/wishlist/
```
Returns all courses in the user's wishlist.

#### Add to Wishlist
```
POST /api/enrollments/wishlist/add/
Body: {"course_id": 1}
```
Adds a course to the wishlist.

#### Remove from Wishlist
```
DELETE /api/enrollments/wishlist/<wishlist_id>/remove/
```
Removes a course from the wishlist.

#### Check Wishlist Status
```
GET /api/enrollments/wishlist/check/<course_id>/
```
Checks if a course is in the wishlist.

### Statistics & Analytics

#### Enrollment Statistics
```
GET /api/enrollments/stats/
```
Returns overall enrollment statistics for the user.

**Response:**
```json
{
  "total_enrollments": 5,
  "active_enrollments": 3,
  "completed_enrollments": 2,
  "canceled_enrollments": 0,
  "total_courses_enrolled": 5,
  "average_progress": 65.5,
  "total_watch_time_hours": 12.5
}
```

#### Learning Dashboard
```
GET /api/enrollments/learning-dashboard/
```
Returns detailed progress for all active enrollments.

### Instructor Analytics

#### Export Lesson Analytics
```
GET /api/enrollments/instructor/courses/<course_id>/lesson-analytics-csv/
```
Exports lesson analytics as CSV (instructors only).

## Services

### mark_lesson_completed(enrollment, lesson)
Marks a lesson as completed for an enrollment.

### check_and_complete_course(enrollment)
Checks if all lessons are completed and auto-completes the course.

### auto_complete_lesson(progress)
Checks if lesson watch time exceeds threshold (80%) for auto-completion.

### get_resume_lesson(enrollment)
Returns the next incomplete lesson for an enrollment.

### get_next_lesson(enrollment, current_lesson)
Returns the next lesson after the current one.

### require_active_enrollment(user, course)
Validates that a user has an active enrollment for a course.

## Constants

### LESSON_COMPLETION_THRESHOLD
```python
LESSON_COMPLETION_THRESHOLD = 0.8  # 80%
```
Percentage of lesson duration that must be watched for auto-completion.

## Admin Interface

### Enrollment Admin
- List view with status badges and progress bars
- Filter by status, completion, date
- Search by user and course
- Inline lesson progress display
- Actions: Mark as completed/active/canceled
- Visual progress indicators

### LessonProgress Admin
- List view with watch time and completion status
- Filter by completion status, dates
- Search by user, lesson, course
- Visual completion badges
- Action: Mark as completed

### Wishlist Admin
- List view with course details and price
- Filter by date, course level, category
- Search by user and course
- Readonly fields for data integrity

## Signals

The app uses Django signals to:
- Auto-issue certificates when courses are completed
- Update enrollment status based on progress
- Track lesson completion timestamps

## Testing

Run tests with:
```bash
python manage.py test enrollments
```

### Test Coverage
- Model creation and constraints
- Enrollment services (completion, progress)
- API endpoints (enrollment, wishlist, progress)
- Auto-completion logic
- Navigation (next lesson, resume)

## Usage Examples

### Enrolling in a Course
```python
from enrollments.models import Enrollment
from courses.models import Course
from accounts.models import User

user = User.objects.get(email='student@example.com')
course = Course.objects.get(id=1)

enrollment = Enrollment.objects.create(user=user, course=course)
```

### Tracking Lesson Progress
```python
from enrollments.services import mark_lesson_completed

lesson = Lesson.objects.get(id=1)
mark_lesson_completed(enrollment, lesson)
```

### Adding to Wishlist
```python
from enrollments.models import Wishlist

wishlist = Wishlist.objects.create(user=user, course=course)
```

## Security

- All endpoints require authentication
- Users can only access their own enrollments and progress
- Instructors can only access analytics for their own courses
- Proper permission checks on all API endpoints

## Performance Optimization

- Select_related used for foreign keys
- Prefetch_related for reverse relationships
- Indexed fields for common queries
- Efficient aggregation queries for statistics

## Future Enhancements

- Learning streaks and achievements
- Personalized learning recommendations
- Social features (study groups, forums)
- Offline progress syncing
- Certificate generation integration
- Email notifications for completions
- Progress reminders
