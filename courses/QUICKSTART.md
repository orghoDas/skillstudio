# Courses App Quick Start Guide

## Installation

1. **Add to INSTALLED_APPS** in `settings.py`:
```python
INSTALLED_APPS = [
    ...
    'courses',
    'enrollments',
    ...
]
```

2. **Run migrations**:
```bash
python manage.py makemigrations courses
python manage.py migrate courses
```

3. **Include URLs** in your main `urls.py`:
```python
urlpatterns = [
    path('api/v1/courses/', include('courses.urls')),
]
```

## Quick Examples

### 1. Create a Category (Admin/Instructor)

**Request:**
```bash
POST /api/v1/courses/categories/
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "name": "Web Development",
  "slug": "web-development",
  "description": "Learn web development skills"
}
```

### 2. Create a Course (Instructor)

**Request:**
```bash
POST /api/v1/courses/create/
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "title": "Complete Web Development Bootcamp",
  "slug": "complete-web-dev-bootcamp",
  "description": "Master HTML, CSS, JavaScript, and more",
  "category": 1,
  "price": "199.99",
  "level": "beginner",
  "language": "English",
  "requirements": ["Basic computer skills", "Internet connection"],
  "learning_objectives": ["Build responsive websites", "Master JavaScript"],
  "target_audience": ["Aspiring web developers", "Career changers"]
}
```

**Response:**
```json
{
  "id": 1,
  "title": "Complete Web Development Bootcamp",
  "slug": "complete-web-dev-bootcamp",
  "status": "draft",
  "is_published": false,
  "created_at": "2024-01-15T10:00:00Z"
}
```

### 3. Add a Module

**Request:**
```bash
POST /api/v1/courses/complete-web-dev-bootcamp/modules/create/
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "title": "HTML Fundamentals",
  "description": "Learn the basics of HTML",
  "order": 1
}
```

### 4. Add a Lesson

**Request:**
```bash
POST /api/v1/courses/complete-web-dev-bootcamp/modules/1/lessons/create/
Authorization: Bearer <your_token>
Content-Type: application/json

{
  "title": "Introduction to HTML",
  "content": "HTML stands for HyperText Markup Language...",
  "video_url": "https://youtube.com/watch?v=example",
  "order": 1,
  "duration": 15,
  "content_type": "video",
  "is_preview": true
}
```

### 5. Submit Course for Review

**Request:**
```bash
POST /api/v1/courses/complete-web-dev-bootcamp/submit-review/
Authorization: Bearer <your_token>
```

**Response:**
```json
{
  "message": "Course submitted for review successfully",
  "status": "under_review"
}
```

### 6. Publish Course (Admin Only)

**Request:**
```bash
POST /api/v1/courses/complete-web-dev-bootcamp/publish/
Authorization: Bearer <admin_token>
```

**Response:**
```json
{
  "message": "Course published successfully",
  "status": "published",
  "published_at": "2024-01-16T12:00:00Z"
}
```

### 7. Browse Published Courses (Public)

**Request:**
```bash
GET /api/v1/courses/?level=beginner&ordering=-created_at
```

**Response:**
```json
{
  "count": 50,
  "next": "http://api.example.com/api/v1/courses/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Complete Web Development Bootcamp",
      "slug": "complete-web-dev-bootcamp",
      "instructor": {
        "id": 5,
        "name": "John Doe",
        "email": "john@example.com"
      },
      "category": "Web Development",
      "price": "199.99",
      "level": "beginner",
      "enrollment_count": 1250
    }
  ]
}
```

### 8. Get Course Details

**Request:**
```bash
GET /api/v1/courses/complete-web-dev-bootcamp/
```

**Response:**
```json
{
  "id": 1,
  "title": "Complete Web Development Bootcamp",
  "slug": "complete-web-dev-bootcamp",
  "description": "Master HTML, CSS, JavaScript, and more",
  "instructor": {
    "id": 5,
    "name": "John Doe"
  },
  "category": {
    "id": 1,
    "name": "Web Development"
  },
  "price": "199.99",
  "level": "beginner",
  "enrollment_count": 1250,
  "total_lessons": 45,
  "estimated_duration": 1800,
  "modules": [
    {
      "id": 1,
      "title": "HTML Fundamentals",
      "total_lessons": 10,
      "total_duration": 300,
      "lessons": [...]
    }
  ]
}
```

### 9. Enroll in Course (Student)

**Request:**
```bash
POST /api/v1/enrollments/enroll/
Authorization: Bearer <student_token>
Content-Type: application/json

{
  "course": 1
}
```

### 10. Complete a Lesson (Enrolled Student)

**Request:**
```bash
POST /api/v1/courses/complete-web-dev-bootcamp/lessons/1/complete/
Authorization: Bearer <student_token>
```

**Response:**
```json
{
  "message": "Lesson marked as complete",
  "progress_percentage": 2.2,
  "next_lesson": {
    "id": 2,
    "title": "HTML Tags"
  }
}
```

### 11. View Course Analytics (Instructor)

**Request:**
```bash
GET /api/v1/courses/complete-web-dev-bootcamp/analytics/
Authorization: Bearer <instructor_token>
```

**Response:**
```json
{
  "total_enrollments": 1250,
  "active_enrollments": 800,
  "completed_enrollments": 450,
  "average_progress": 65.5,
  "completion_rate": 36.0,
  "revenue": "249875.00"
}
```

### 15. Instructor Dashboard

**Request:**
```bash
GET /api/v1/courses/instructor/dashboard/
Authorization: Bearer <instructor_token>
```

**Response:**
```json
{
  "total_courses": 5,
  "published_courses": 3,
  "draft_courses": 2,
  "total_enrollments": 3500,
  "total_revenue": "698000.00",
  "courses": [
    {
      "id": 1,
      "title": "Complete Web Development Bootcamp",
      "enrollments": 1250,
      "revenue": "249875.00",
      "rating": 4.8
    }
  ]
}
```

## Common Search & Filter Queries

### Search by Keyword
```bash
GET /api/v1/courses/?search=python
```

### Filter by Category
```bash
GET /api/v1/courses/?category=1
```

### Filter by Level
```bash
GET /api/v1/courses/?level=beginner
```

### Filter by Price Range
```bash
GET /api/v1/courses/?min_price=0&max_price=100
```

### Get Free Courses
```bash
GET /api/v1/courses/?is_free=true
```

### Sort by Price (Low to High)
```bash
GET /api/v1/courses/?ordering=price
```

### Sort by Newest
```bash
GET /api/v1/courses/?ordering=-created_at
```

### Combined Filters
```bash
GET /api/v1/courses/?category=1&level=beginner&ordering=-created_at&is_free=true
```

## Authentication

All authenticated endpoints require a JWT token in the Authorization header:

```bash
Authorization: Bearer <your_access_token>
```

Get tokens from the accounts app:
```bash
POST /api/v1/accounts/login/
{
  "email": "user@example.com",
  "password": "yourpassword"
}
```

## Permissions Summary

| Endpoint | Permission |
|----------|------------|
| List Courses | Public |
| Course Detail | Public |
| Create Course | Instructor/Admin |
| Update Course | Course Instructor/Admin |
| Delete Course | Course Instructor/Admin |
| Submit for Review | Course Instructor |
| Publish Course | Admin Only |
| Create Module/Lesson | Course Instructor/Admin |
| Complete Lesson | Enrolled Student |
| View Analytics | Course Instructor/Admin |
| Instructor Dashboard | Instructor/Admin |
| Admin Stats | Admin Only |

## Tips

1. **Course Workflow**: Always create courses in this order:
   - Create Course (draft)
   - Add Modules
   - Add Lessons to Modules
   - Submit for Review
   - Admin Publishes

2. **Testing**: Use `is_preview=true` for lessons to make them publicly accessible without enrollment

3. **Pricing**: Set `price=0` or `discount_price=0` for free courses

4. **Content Types**: Use appropriate content types (video, text, quiz) for better organization

5. **Order**: Always set proper `order` values for modules and lessons to maintain sequence

## Troubleshooting

**Q: Can't create a course**
- Check if user has instructor or admin role
- Verify authentication token is valid

**Q: Course not appearing in listings**
- Ensure course is published (`is_published=true`)
- Check if course status is 'published'

**Q: Can't review a course**
- Verify student is enrolled in the course
- Check if student already reviewed the course (one review per student)

**Q: Lesson completion not working**
- Ensure user is enrolled in the course
- Verify lesson belongs to the correct course

## Next Steps

- Review the full [README.md](README.md) for detailed documentation
- Check the [tests.py](tests.py) for more usage examples
- Explore the admin interface at `/admin/courses/`
- Integrate with enrollments app for student progress tracking
