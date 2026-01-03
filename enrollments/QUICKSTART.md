# Enrollments App - Quick Start Guide

## Installation & Setup

The enrollments app is already integrated into the SkillStudio project. No additional installation required.

## Basic Usage

### 1. Enrolling in a Course

**Via API:**
```bash
curl -X POST http://localhost:8000/api/enrollments/enroll/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"course_id": 1}'
```

**Via Python:**
```python
from enrollments.models import Enrollment
from courses.models import Course
from django.contrib.auth import get_user_model

User = get_user_model()

user = User.objects.get(email='student@example.com')
course = Course.objects.get(id=1)

enrollment = Enrollment.objects.create(
    user=user,
    course=course,
    status='active'
)
```

### 2. Tracking Lesson Progress

**Update Watch Time:**
```bash
curl -X PATCH http://localhost:8000/api/enrollments/lessons/1/watch-time/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"watch_time": 450}'
```

**Mark Lesson Complete:**
```bash
curl -X POST http://localhost:8000/api/enrollments/lessons/1/complete/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 3. Managing Wishlist

**Add to Wishlist:**
```bash
curl -X POST http://localhost:8000/api/enrollments/wishlist/add/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"course_id": 1}'
```

**View Wishlist:**
```bash
curl -X GET http://localhost:8000/api/enrollments/wishlist/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Checking Progress

**Get Course Progress:**
```bash
curl -X GET http://localhost:8000/api/enrollments/courses/1/progress/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Get Learning Dashboard:**
```bash
curl -X GET http://localhost:8000/api/enrollments/learning-dashboard/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Common Workflows

### Student Learning Flow

1. **Browse and Wishlist Courses**
   ```python
   # Add course to wishlist
   POST /api/enrollments/wishlist/add/
   {"course_id": 1}
   ```

2. **Enroll in Course**
   ```python
   # Enroll in course
   POST /api/enrollments/enroll/
   {"course_id": 1}
   ```

3. **Start Learning**
   ```python
   # Get first/resume lesson
   GET /api/enrollments/courses/1/resume-lesson/
   ```

4. **Track Progress**
   ```python
   # Update watch time as student watches
   PATCH /api/enrollments/lessons/1/watch-time/
   {"watch_time": 450}
   
   # Lesson auto-completes at 80% watched
   ```

5. **Continue Learning**
   ```python
   # Get next lesson
   GET /api/enrollments/courses/1/lessons/1/next/
   ```

6. **View Progress**
   ```python
   # Check overall progress
   GET /api/enrollments/courses/1/progress/
   ```

### Instructor Workflow

1. **View Dashboard**
   ```python
   GET /api/enrollments/instructor/dashboard/
   ```

2. **Export Analytics**
   ```python
   # Export lesson analytics
   GET /api/enrollments/instructor/courses/1/lesson-analytics-csv/
   ```

## Configuration

### Completion Threshold

Adjust the auto-completion threshold in `enrollments/constants.py`:

```python
LESSON_COMPLETION_THRESHOLD = 0.8  # 80%
```

### Admin Interface

Access the admin interface at:
- Enrollments: `/admin/enrollments/enrollment/`
- Lesson Progress: `/admin/enrollments/lessonprogress/`
- Wishlist: `/admin/enrollments/wishlist/`

## Testing

Run all enrollment tests:
```bash
python manage.py test enrollments
```

Run specific test class:
```bash
python manage.py test enrollments.tests.EnrollmentAPITest
```

Run specific test:
```bash
python manage.py test enrollments.tests.EnrollmentAPITest.test_enroll_in_course
```

## Troubleshooting

### Common Issues

**1. "Already enrolled" error**
- Check if enrollment exists but is canceled
- Enrollment automatically reactivates on re-enrollment

**2. Lesson not auto-completing**
- Verify watch_time >= duration * 0.8
- Check lesson duration_seconds is set
- Ensure lesson is not marked as free

**3. Course not auto-completing**
- All non-free lessons must be completed
- Check enrollment status is 'active'
- Verify lesson_progress records exist

### Debug Commands

**Check enrollment status:**
```python
python manage.py shell
>>> from enrollments.models import Enrollment
>>> e = Enrollment.objects.get(user__email='student@example.com', course_id=1)
>>> print(f"Status: {e.status}, Completed: {e.is_completed}")
```

**Check lesson progress:**
```python
>>> from enrollments.models import LessonProgress
>>> progress = LessonProgress.objects.filter(enrollment=e)
>>> for p in progress:
...     print(f"Lesson {p.lesson.id}: {p.watch_time}/{p.lesson.duration_seconds} - Completed: {p.is_completed}")
```

**Verify completion:**
```python
>>> from enrollments.services import check_and_complete_course
>>> result = check_and_complete_course(e)
>>> print(f"Course completed: {result}")
```

## API Response Examples

### Enrollment Detail
```json
{
  "id": 1,
  "course": {
    "id": 1,
    "title": "Python Fundamentals",
    "description": "Learn Python from scratch",
    "thumbnail_url": "https://example.com/thumb.jpg",
    "level": "beginner",
    "language": "English",
    "instructor": {
      "id": 2,
      "name": "John Smith",
      "bio": "Python expert with 10 years experience"
    }
  },
  "status": "active",
  "is_completed": false,
  "enrolled_at": "2024-01-15T10:30:00Z",
  "completed_at": null,
  "progress": {
    "total_lessons": 20,
    "completed_lessons": 5,
    "progress_percentage": 25.0,
    "total_duration_seconds": 7200,
    "watched_time_seconds": 1800
  },
  "next_lesson": {
    "id": 6,
    "title": "Functions in Python",
    "module_id": 2,
    "module_title": "Python Basics",
    "position": 1
  }
}
```

### Learning Statistics
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

## Integration Examples

### With Certificates App
```python
from enrollments.services import check_and_complete_course
from certificates.services import issue_certificate

# After completing all lessons
if check_and_complete_course(enrollment):
    # Certificate is automatically issued via signal
    # Or manually:
    issue_certificate(enrollment)
```

### With Analytics App
```python
from enrollments.models import Enrollment, LessonProgress
from django.db.models import Count, Avg

# Get enrollment statistics
stats = Enrollment.objects.aggregate(
    total=Count('id'),
    completed=Count('id', filter=Q(status='completed'))
)

# Get average progress
avg_progress = LessonProgress.objects.aggregate(
    avg_completion=Avg('watch_time')
)
```

## Best Practices

1. **Always use services for business logic**
   - Use `mark_lesson_completed()` instead of direct updates
   - Use `check_and_complete_course()` after lesson completion

2. **Handle edge cases**
   - Check for active enrollment before tracking progress
   - Validate lesson belongs to enrolled course
   - Handle zero-duration lessons

3. **Optimize queries**
   - Use select_related for foreign keys
   - Prefetch lesson progress for multiple enrollments
   - Aggregate at database level for statistics

4. **Security**
   - Always verify user owns enrollment
   - Check course is published before enrollment
   - Validate lesson access permissions

## Support

For issues or questions:
- Check the main README.md
- Review test cases for examples
- Check admin interface for data verification
