# Analytics Application

## Overview
The Analytics application provides comprehensive data tracking, analysis, and reporting capabilities for the Skillstudio platform. It tracks user interactions, course performance, instructor earnings, student progress, and platform-wide metrics.

## Features

### 📊 Course Analytics
- **Performance Metrics**: Enrollments, completions, watch time, revenue
- **Engagement Analysis**: Drop-off rates, progress tracking, lesson analytics
- **Rating Analytics**: Average ratings, review counts, sentiment analysis
- **Enrollment Trends**: Track enrollment growth over time
- **Revenue Tracking**: Course-level revenue and pricing analytics

### 👨‍🏫 Instructor Analytics
- **Dashboard Overview**: Complete instructor performance dashboard
- **Earnings Breakdown**: Detailed revenue reports by course and time period
- **Student Metrics**: Total students, engagement, and completion rates
- **Course Comparison**: Compare performance across all instructor courses
- **Rating Analysis**: Average ratings and review statistics

### 🎓 Student Analytics
- **Learning Dashboard**: Personal learning analytics and progress
- **Course Progress**: Detailed progress reports for each enrolled course
- **Learning Time**: Total watch time and engagement metrics
- **Achievements**: Certificates, completions, and milestones
- **Recent Activity**: Timeline of recent learning activities

### 🎪 Event Analytics
- **Registration Metrics**: Total registrations and confirmed attendees
- **Attendance Tracking**: Attendance rates and no-show analysis
- **Revenue Reports**: Event revenue and ticket sales
- **Engagement Metrics**: Event ratings and feedback analysis

### 🌍 Platform-Wide Analytics
- **Overview Dashboard**: Platform-wide metrics and KPIs
- **Growth Metrics**: User growth, enrollment trends, revenue growth
- **Trending Content**: Identify trending courses and popular topics
- **Search Analytics**: Search queries, popular searches, zero-result rates
- **User Behavior**: Interaction tracking and engagement patterns

### 📈 Advanced Features
- **Historical Snapshots**: Daily snapshots for trend analysis
- **Interaction Tracking**: Track all user interactions across the platform
- **Predictive Analytics**: (Basis for AI recommendations)
- **Custom Reports**: Flexible date ranges and filtering
- **Real-time Metrics**: Up-to-date analytics and statistics

## Models

### CourseAnalyticsSnapshot
Daily snapshot of course analytics for historical tracking.

**Fields:**
- `course`: Foreign key to Course
- `snapshot_date`: Date of the snapshot
- `total_enrollments`: Total enrollments on this date
- `total_completions`: Total completions
- `total_watch_minutes`: Total watch time in minutes
- `unique_viewers`: Number of unique students
- `average_rating`: Average rating
- `total_revenue`: Total revenue earned
- `created_at`: Timestamp

### UserInteraction
Tracks all user interactions across the platform.

**Fields:**
- `user`: User who performed the action
- `course`: Related course (if applicable)
- `event`: Related event (if applicable)
- `action`: Type of interaction (view, enroll, complete, etc.)
- `metadata`: Additional JSON data
- `session_id`: Session identifier
- `ip_address`: User's IP address
- `user_agent`: Browser user agent
- `created_at`: Timestamp

**Tracked Actions:**
- `view_course`, `enroll_course`, `complete_lesson`
- `start_lesson`, `submit_quiz`, `post_review`
- `bookmark_course`, `search`, `view_event`
- `register_event`, `join_circle`, `create_post`, `like_post`

### InstructorAnalytics
Aggregated analytics for instructors (updated periodically).

**Fields:**
- `instructor`: One-to-one with instructor user
- `total_courses`: Number of courses
- `total_students`: Unique student count
- `total_revenue`: Total earnings
- `average_rating`: Average rating across all courses
- `total_reviews`: Total review count
- `total_completions`: Total course completions
- `last_updated`: Last update timestamp

### LessonAnalytics
Analytics for individual lessons.

**Fields:**
- `lesson`: One-to-one with Lesson
- `total_views`: Number of views
- `total_completions`: Number of completions
- `average_watch_time`: Average watch time in seconds
- `drop_off_rate`: Percentage drop-off rate
- `last_updated`: Last update timestamp

### EventAnalytics
Analytics for events.

**Fields:**
- `event`: One-to-one with Event
- `total_registrations`: Total registrations
- `total_attendees`: Actual attendees
- `attendance_rate`: Attendance percentage
- `average_rating`: Average event rating
- `total_revenue`: Event revenue
- `last_updated`: Last update timestamp

### SearchQuery
Tracks search queries for analytics and recommendations.

**Fields:**
- `user`: User who searched (optional)
- `query`: Search query string
- `results_count`: Number of results returned
- `clicked_result`: Course clicked from results (if any)
- `filters`: JSON field for applied filters
- `created_at`: Timestamp

### DailyPlatformMetrics
Daily aggregated platform-wide metrics.

**Fields:**
- `date`: Unique date
- `total_users`: Total user count
- `new_users`: New users on this date
- `active_users`: Active user count
- `total_enrollments`: Total enrollments
- `new_enrollments`: New enrollments on this date
- `total_completions`: Total completions
- `total_revenue`: Total revenue
- `total_courses`: Total course count
- `total_events`: Total event count
- `created_at`: Timestamp

## API Endpoints

### Instructor Analytics
```
GET /api/analytics/instructor/dashboard/                    # Complete dashboard
GET /api/analytics/instructor/course/{id}/                  # Course analytics
GET /api/analytics/instructor/courses/comparison/           # Compare courses
GET /api/analytics/instructor/course/{id}/dropoff/          # Lesson dropoff analysis
GET /api/analytics/instructor/earnings/                     # Earnings breakdown
GET /api/analytics/instructor/lesson/{id}/                  # Lesson analytics
```

### Student Analytics
```
GET /api/analytics/student/dashboard/                       # Student dashboard
GET /api/analytics/student/course/{id}/progress/            # Course progress
```

### Event Analytics
```
GET /api/analytics/event/{id}/                              # Event analytics
```

### Platform Analytics (Admin)
```
GET /api/analytics/platform/                                # Platform overview
GET /api/analytics/trending/                                # Trending courses
GET /api/analytics/search/                                  # Search analytics
```

### Public Analytics
```
GET /api/analytics/public/course/{id}/                      # Public course stats
```

### Interaction Tracking
```
POST /api/analytics/track/                                  # Track interaction
```

## Usage Examples

### Get Course Analytics (Instructor)
```python
response = client.get('/api/analytics/instructor/course/123/')

# Response includes:
# - total_enrollments
# - completion_rate
# - average_progress
# - drop_off analysis
# - revenue data
# - rating statistics
# - enrollment trends
```

### Get Student Progress Report
```python
response = client.get('/api/analytics/student/course/123/progress/')

# Response includes:
# - progress_percentage
# - completed_lessons
# - total_watch_time
# - lesson-by-lesson breakdown
# - last_accessed timestamps
```

### Track User Interaction
```python
response = client.post(
    '/api/analytics/track/',
    {
        'action': 'complete_lesson',
        'course_id': 123,
        'metadata': {
            'lesson_id': 456,
            'watch_time': 1800
        }
    }
)
```

### Get Instructor Earnings
```python
response = client.get(
    '/api/analytics/instructor/earnings/',
    params={
        'start_date': '2026-01-01',
        'end_date': '2026-01-31'
    }
)

# Response includes:
# - total_earnings
# - total_transactions
# - breakdown by course
# - breakdown by month
```

### Get Trending Courses
```python
response = client.get(
    '/api/analytics/trending/',
    params={
        'limit': 10,
        'days': 7
    }
)
```

## Services

Comprehensive business logic in `services.py`:

### Course Analytics
- `get_course_analytics(course_id, instructor=None)`
- `get_lesson_analytics(lesson_id)`
- `get_course_comparison(instructor)`
- `get_lesson_dropoff_analysis(course_id, instructor=None)`

### Instructor Analytics
- `get_instructor_analytics(instructor)`
- `get_instructor_earnings_breakdown(instructor, start_date=None, end_date=None)`

### Student Analytics
- `get_student_analytics(student)`
- `get_student_progress_report(student, course_id)`

### Event Analytics
- `get_event_analytics(event_id)`

### Platform Analytics
- `get_platform_overview(days=30)`
- `get_trending_courses(limit=10, days=7)`
- `get_search_analytics(days=30)`

### Tracking & Snapshots
- `track_user_interaction(user, action, **kwargs)`
- `create_daily_snapshot(date=None)`
- `create_daily_platform_metrics(date=None)`

## Permissions

### Instructor Analytics
- Requires: Authenticated + `IsInstructor` permission
- Scope: Can only view analytics for their own courses

### Student Analytics
- Requires: Authenticated
- Scope: Can only view their own analytics

### Platform Analytics
- Requires: Authenticated + `IsAdmin` permission
- Scope: Full platform access

### Public Analytics
- No authentication required
- Limited to non-sensitive metrics

## Background Tasks (Recommended)

For optimal performance, schedule these tasks:

```python
# Daily (recommended: 2 AM)
from analytics.services import create_daily_snapshot, create_daily_platform_metrics

# Create snapshots for all courses
create_daily_snapshot()

# Create platform metrics
create_daily_platform_metrics()
```

Using Celery:
```python
from celery import shared_task

@shared_task
def daily_analytics_snapshot():
    create_daily_snapshot()
    create_daily_platform_metrics()
```

## Testing

Run tests:
```bash
python manage.py test analytics
```

Tests cover:
- Model creation and relationships
- Service function accuracy
- API endpoint authorization
- Data aggregation logic
- Interaction tracking

## Performance Optimization

### Database Indexes
All models include optimized indexes for:
- Date-based queries
- User lookups
- Course/event relationships
- Action type filtering

### Query Optimization
- Uses `select_related()` for foreign keys
- Uses `annotate()` for aggregations
- Limits result sets appropriately
- Caches frequently accessed data

### Recommended Caching
```python
# Cache expensive analytics for 1 hour
from django.core.cache import cache

def get_course_analytics(course_id):
    cache_key = f'course_analytics_{course_id}'
    cached = cache.get(cache_key)
    
    if cached:
        return cached
    
    # Calculate analytics...
    cache.set(cache_key, result, 3600)  # 1 hour
    return result
```

## Integration with Other Apps

- **Courses**: Course and lesson performance metrics
- **Enrollments**: Student progress and engagement
- **Payments**: Revenue and earnings analytics
- **Events**: Event performance tracking
- **Accounts**: User behavior and interaction patterns
- **AI Recommender**: Uses interaction data for recommendations

## Data Privacy

- Student data is only visible to the student themselves and admins
- Instructor data shows only aggregated student metrics (no PII)
- Public endpoints return only non-sensitive information
- IP addresses and session data are handled securely

## Future Enhancements

- Real-time analytics dashboard
- Advanced predictive analytics
- Machine learning-based insights
- Customizable report builder
- Data export in multiple formats (CSV, PDF, Excel)
- Integration with external analytics tools (Google Analytics, Mixpanel)
- A/B testing framework
- Cohort analysis
- Funnel analysis
