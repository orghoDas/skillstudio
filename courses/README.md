# Courses App Documentation

## Overview

The courses app is the core module of SkillStudio, providing comprehensive course management functionality including course creation, content organization, reviews, and analytics. It supports the complete course lifecycle from draft creation to publishing and student enrollment.

## Features

### Course Management
- **CRUD Operations**: Create, read, update, and delete courses
- **Publishing Workflow**: Draft → Under Review → Published → Archived
- **Version Control**: Track course versions and changes
- **Multi-level Content**: Organize content with Modules and Lessons
- **Rich Content**: Support for video, text, quiz, and assignment content types

### Content Organization
- **Categories**: Organize courses by subject area
- **Tags**: Add multiple tags for better discoverability
- **Modules**: Group related lessons together
- **Lessons**: Individual learning units with various content types
- **Resources**: Attach supplementary materials to lessons

### Reviews & Ratings
- **Student Reviews**: Enrolled students can review courses
- **Rating System**: 1-5 star ratings with comments
- **Rating Statistics**: Average ratings and distribution
- **Review Management**: Update and delete reviews

### Analytics
- **Instructor Dashboard**: View course performance metrics
- **Course Analytics**: Detailed statistics per course
- **Admin Statistics**: System-wide course metrics
- **Enrollment Tracking**: Monitor student enrollments

## Models

### Course
Main course model with all course information.

**Fields:**
- `title` - Course title
- `slug` - URL-friendly identifier
- `description` - Full course description
- `short_description` - Brief summary (optional)
- `instructor` - Course creator (ForeignKey to User)
- `category` - Course category
- `tags` - Multiple tags (ManyToMany)
- `thumbnail` - Course image
- `video_url` - Promotional video
- `price` - Course price (Decimal)
- `discount_price` - Discounted price (optional)
- `level` - Difficulty: beginner, intermediate, advanced
- `language` - Course language
- `status` - Workflow status: draft, under_review, published, archived
- `is_published` - Publication flag
- `published_at` - Publication timestamp
- `requirements` - Prerequisites (JSON)
- `learning_objectives` - Course goals (JSON)
- `target_audience` - Intended students (JSON)
- `estimated_duration` - Total duration in minutes
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

**Properties:**
- `enrollment_count` - Total enrolled students
- `average_rating` - Average review rating
- `total_reviews` - Total number of reviews
- `total_lessons` - Total lessons across all modules

### Module
Grouping of related lessons within a course.

**Fields:**
- `course` - Parent course (ForeignKey)
- `title` - Module title
- `description` - Module description (optional)
- `order` - Display order
- `is_published` - Publication flag
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

**Properties:**
- `total_lessons` - Number of lessons in module
- `total_duration` - Combined duration of all lessons

### Lesson
Individual learning unit within a module.

**Fields:**
- `module` - Parent module (ForeignKey)
- `title` - Lesson title
- `content` - Main lesson content (text)
- `video_url` - Video link (optional)
- `order` - Display order within module
- `duration` - Lesson duration in minutes
- `is_preview` - Free preview flag
- `is_published` - Publication flag
- `content_type` - Type: video, text, quiz, assignment
- `created_at` - Creation timestamp
- `updated_at` - Last update timestamp

### Category
Course categorization.

**Fields:**
- `name` - Category name
- `slug` - URL-friendly identifier
- `description` - Category description
- `parent` - Parent category (optional)
- `icon` - Category icon
- `is_active` - Active status
- `created_at` - Creation timestamp

### Tag
Course tagging for enhanced search.

**Fields:**
- `name` - Tag name
- `slug` - URL-friendly identifier
- `created_at` - Creation timestamp

### LessonResource
Supplementary materials for lessons.

**Fields:**
- `lesson` - Parent lesson (ForeignKey)
- `title` - Resource title
- `file` - Uploaded file
- `url` - External resource link (optional)
- `resource_type` - Type: pdf, video, link, code, other
- `order` - Display order
- `created_at` - Upload timestamp

### CourseVersion
Version tracking for courses.

**Fields:**
- `course` - Parent course (ForeignKey)
- `version_number` - Version identifier
- `changes` - Description of changes
- `created_by` - User who created version
- `created_at` - Version timestamp

## API Endpoints

### Course Endpoints

#### List Courses
```
GET /api/v1/courses/
```
**Query Parameters:**
- `search` - Search in title/description
- `category` - Filter by category ID
- `level` - Filter by difficulty level
- `min_price` / `max_price` - Price range
- `instructor` - Filter by instructor ID
- `is_free` - Filter free courses (true/false)
- `ordering` - Sort by: created_at, -created_at, price, -price, title

**Response:** Paginated list of courses

#### Course Detail
```
GET /api/v1/courses/{slug}/
```
**Response:** Complete course details with modules and lessons

#### Create Course
```
POST /api/v1/courses/create/
```
**Permission:** Instructor or Admin only

**Request Body:**
```json
{
  "title": "Python Fundamentals",
  "slug": "python-fundamentals",
  "description": "Learn Python from scratch",
  "category": 1,
  "price": "99.99",
  "level": "beginner",
  "language": "English"
}
```

#### Update Course
```
PATCH /api/v1/courses/{slug}/update/
```
**Permission:** Course instructor or Admin

#### Delete Course
```
DELETE /api/v1/courses/{slug}/delete/
```
**Permission:** Course instructor or Admin

#### Submit for Review
```
POST /api/v1/courses/{slug}/submit-review/
```
**Permission:** Course instructor
**Effect:** Changes status from draft to under_review

#### Publish Course
```
POST /api/v1/courses/{slug}/publish/
```
**Permission:** Admin only
**Effect:** Changes status to published, sets is_published=True

#### Unpublish Course
```
POST /api/v1/courses/{slug}/unpublish/
```
**Permission:** Admin only
**Effect:** Changes status to archived, sets is_published=False

### Module Endpoints

#### List Modules
```
GET /api/v1/courses/{course_slug}/modules/
```

#### Module Detail
```
GET /api/v1/courses/{course_slug}/modules/{id}/
```

#### Create Module
```
POST /api/v1/courses/{course_slug}/modules/create/
```
**Permission:** Course instructor or Admin

**Request Body:**
```json
{
  "title": "Introduction to Python",
  "description": "Getting started with Python",
  "order": 1
}
```

#### Update Module
```
PATCH /api/v1/courses/{course_slug}/modules/{id}/update/
```

#### Delete Module
```
DELETE /api/v1/courses/{course_slug}/modules/{id}/delete/
```

### Lesson Endpoints

#### Lesson Detail
```
GET /api/v1/courses/{course_slug}/lessons/{id}/
```

#### Create Lesson
```
POST /api/v1/courses/{course_slug}/modules/{module_id}/lessons/create/
```
**Permission:** Course instructor or Admin

**Request Body:**
```json
{
  "title": "Variables and Data Types",
  "content": "Learn about Python variables...",
  "video_url": "https://youtube.com/watch?v=...",
  "order": 1,
  "duration": 15,
  "content_type": "video",
  "is_preview": false
}
```

#### Update Lesson
```
PATCH /api/v1/courses/{course_slug}/lessons/{id}/update/
```

#### Delete Lesson
```
DELETE /api/v1/courses/{course_slug}/lessons/{id}/delete/
```

#### Mark Lesson Complete
```
POST /api/v1/courses/{course_slug}/lessons/{id}/complete/
```
**Permission:** Enrolled student

### Review Endpoints

#### List Reviews
```
GET /api/v1/courses/{course_slug}/reviews/
```

#### Create Review
```
POST /api/v1/courses/{course_slug}/reviews/create/
```
**Permission:** Enrolled student

**Request Body:**
```json
{
  "rating": 5,
  "title": "Excellent Course",
  "comment": "Very informative and well structured"
}
```

#### Update Review
```
PATCH /api/v1/courses/{course_slug}/reviews/{id}/update/
```
**Permission:** Review author

#### Delete Review
```
DELETE /api/v1/courses/{course_slug}/reviews/{id}/delete/
```
**Permission:** Review author or Admin

#### Rating Statistics
```
GET /api/v1/courses/{course_slug}/reviews/stats/
```

**Response:**
```json
{
  "average_rating": 4.5,
  "total_reviews": 120,
  "rating_distribution": {
    "5": 80,
    "4": 25,
    "3": 10,
    "2": 3,
    "1": 2
  }
}
```

### Analytics Endpoints

#### Course Analytics
```
GET /api/v1/courses/{course_slug}/analytics/
```
**Permission:** Course instructor or Admin

**Response:**
```json
{
  "total_enrollments": 245,
  "active_enrollments": 180,
  "completed_enrollments": 65,
  "average_progress": 62.5,
  "average_rating": 4.5,
  "total_reviews": 120,
  "completion_rate": 26.5,
  "revenue": "24255.00"
}
```

#### Instructor Dashboard
```
GET /api/v1/courses/instructor/dashboard/
```
**Permission:** Instructor or Admin

**Response:**
```json
{
  "total_courses": 5,
  "published_courses": 3,
  "draft_courses": 2,
  "total_enrollments": 450,
  "total_revenue": "44775.00",
  "average_rating": 4.3,
  "courses": [...]
}
```

#### Admin Statistics
```
GET /api/v1/courses/admin/stats/
```
**Permission:** Admin only

### Curriculum Endpoints

#### Get Full Curriculum
```
GET /api/v1/courses/{course_slug}/curriculum/
```
**Response:** Complete course structure with all modules and lessons

## Permissions

The courses app uses custom permission classes:

- **IsInstructorOrAdmin**: Only instructors and admins can create courses
- **IsCourseInstructor**: Only the course instructor can modify their course
- **IsEnrolledStudent**: Only enrolled students can access certain content
- **IsReviewOwner**: Only review authors can modify their reviews

## Usage Examples

### Creating a Complete Course

```python
from courses.models import Course, Module, Lesson, Category

# Create category
category = Category.objects.create(
    name="Programming",
    slug="programming"
)

# Create course
course = Course.objects.create(
    title="Python Fundamentals",
    slug="python-fundamentals",
    description="Complete Python course for beginners",
    instructor=instructor_user,
    category=category,
    price=Decimal('99.99'),
    level='beginner'
)

# Add module
module = Module.objects.create(
    course=course,
    title="Introduction",
    order=1
)

# Add lesson
lesson = Lesson.objects.create(
    module=module,
    title="Getting Started",
    content="Welcome to Python programming...",
    video_url="https://youtube.com/watch?v=...",
    order=1,
    duration=15,
    content_type='video'
)
```

### Publishing Workflow

```python
# Instructor creates course (status='draft')
course = Course.objects.create(...)

# Instructor submits for review
course.status = 'under_review'
course.save()

# Admin approves and publishes
course.status = 'published'
course.is_published = True
course.published_at = timezone.now()
course.save()
```

### Student Interaction

```python
# Student enrolls
from enrollments.models import Enrollment

enrollment = Enrollment.objects.create(
    user=student_user,
    course=course,
    status='active'
)

# Student completes lesson
from enrollments.models import LessonProgress

progress = LessonProgress.objects.create(
    enrollment=enrollment,
    lesson=lesson,
    is_completed=True,
    completed_at=timezone.now()
)

# Student reviews course
from social.models import Review

review = Review.objects.create(
    user=student_user,
    course=course,
    rating=5,
    title="Great course!",
    comment="Learned a lot from this course"
)
```

## Settings

Add to your `settings.py`:

```python
INSTALLED_APPS = [
    ...
    'courses',
    'enrollments',
    'social',
    ...
]

# Course settings
COURSE_THUMBNAIL_UPLOAD_PATH = 'courses/thumbnails/'
LESSON_RESOURCE_UPLOAD_PATH = 'lessons/resources/'
CATEGORY_ICON_UPLOAD_PATH = 'categories/icons/'

# Pagination
REST_FRAMEWORK = {
    'PAGE_SIZE': 10,
}
```

## Admin Interface

The courses app provides enhanced Django admin interface with:

- **Course Admin**: Status badges, bulk actions, module/lesson inlines
- **Module Admin**: Lesson count display, bulk publishing
- **Lesson Admin**: Duration formatting, content type filters
- **Category Admin**: Hierarchical display, course count
- **Review Admin**: Rating stars display, course links

## Testing

Run tests:

```bash
python manage.py test courses
```

Test coverage includes:
- Model creation and validation
- API endpoint functionality
- Permission checks
- Publishing workflow
- Analytics calculations
- Review system

## Dependencies

- **Django 6.0+**
- **Django REST Framework**
- **Pillow** (for image handling)
- **PostgreSQL** (recommended database)

Related apps:
- `accounts` - User management
- `enrollments` - Student enrollment and progress
- `social` - Reviews and social features
- `instructors` - Instructor management

## Future Enhancements

- [ ] Course certificates upon completion
- [ ] Interactive quizzes and assessments
- [ ] Discussion forums per lesson
- [ ] Live sessions integration
- [ ] Course bundles and packages
- [ ] Advanced analytics with charts
- [ ] Student notes and bookmarks
- [ ] Course recommendations AI
