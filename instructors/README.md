# Instructors App Documentation

## Overview
The instructors app manages instructor profiles, earnings tracking, payout requests, and instructor-specific analytics for the SkillStudio platform. It provides comprehensive tools for instructors to manage their teaching business and track their revenue.

## Features
- **Instructor Profiles**: Extended profiles with professional information
- **Earnings Tracking**: Track revenue from course sales
- **Payout Management**: Request and track payout disbursements
- **Statistics Dashboard**: Real-time statistics on courses, students, and revenue
- **Verification System**: Verify instructors for quality assurance
- **Course Analytics**: Detailed analytics on course performance
- **Student Engagement**: Monitor student progress and engagement

## Models

### InstructorProfile
Extended profile information specific to instructors.

**Fields:**
- `id` (UUIDField, primary key) - Unique identifier
- `user` (OneToOneField to User) - Associated user account
- `bio` (TextField) - Instructor biography
- `headline` (CharField) - Professional headline/tagline
- `website` (URLField) - Personal/professional website
- `linkedin` (URLField) - LinkedIn profile URL
- `twitter` (URLField) - Twitter profile URL
- `expertise_areas` (JSONField) - List of expertise areas/topics
- `years_of_experience` (IntegerField) - Years of teaching/industry experience
- `certifications` (JSONField) - List of professional certifications
- `education` (JSONField) - Educational background
- `total_courses` (IntegerField) - Number of courses created (denormalized)
- `total_students` (IntegerField) - Number of unique students (denormalized)
- `total_revenue` (DecimalField) - Total earnings (denormalized)
- `average_rating` (DecimalField) - Average course rating (denormalized)
- `total_reviews` (IntegerField) - Number of reviews received (denormalized)
- `is_verified` (BooleanField) - Verification status
- `verified_at` (DateTimeField) - Verification timestamp
- `created_at`, `updated_at` (DateTimeField) - Timestamps

**Methods:**
- `verify()` - Mark instructor as verified
- `update_statistics()` - Update denormalized statistics from related models
- `calculate_average_rating()` - Calculate average rating across all courses
- `__str__()` - String representation

**Indexes:**
- user field
- is_verified field
- average_rating (descending)
- total_students (descending)

### InstructorPayout
Tracks payout requests and disbursements to instructors.

**Fields:**
- `id` (UUIDField, primary key) - Unique identifier
- `instructor` (ForeignKey to User) - Instructor requesting payout
- `amount` (DecimalField) - Payout amount
- `status` (CharField) - Status: 'pending', 'processing', 'completed', 'failed', 'canceled'
- `payment_method` (CharField) - Method: 'bank_transfer', 'paypal', 'stripe', 'other'
- `payment_details` (JSONField) - Payment method details (account numbers, etc.)
- `requested_at` (DateTimeField) - When payout was requested
- `processed_at` (DateTimeField) - When payout was processed
- `completed_at` (DateTimeField) - When payout was completed
- `notes` (TextField) - Admin notes or failure reasons
- `created_at`, `updated_at` (DateTimeField) - Timestamps

**Methods:**
- `mark_processing()` - Update status to processing
- `mark_completed()` - Update status to completed
- `mark_failed(reason)` - Update status to failed with reason
- `cancel()` - Cancel pending payout
- `__str__()` - String representation

**Constraints:**
- Status choices validation
- Amount must be positive

## Services

### get_or_create_instructor_profile(user)
Gets or creates an instructor profile for a user.

**Args:**
- `user` - User instance

**Returns:**
- InstructorProfile instance

### update_instructor_profile(user, **kwargs)
Updates instructor profile with provided data.

**Args:**
- `user` - User instance
- `**kwargs` - Fields to update (bio, headline, expertise_areas, etc.)

**Returns:**
- Updated InstructorProfile instance

**Raises:**
- `ValidationError` - If validation fails

### request_payout(instructor, amount, payment_method, payment_details)
Creates a payout request for an instructor.

**Args:**
- `instructor` - User instance (instructor)
- `amount` - Decimal amount to request
- `payment_method` - Payment method choice
- `payment_details` - Dict with payment details

**Returns:**
- InstructorPayout instance

**Raises:**
- `ValidationError` if:
  - Amount exceeds available balance
  - Payment details are invalid
  - Previous payout is still pending

**Validations:**
- Ensures instructor has sufficient balance
- Validates payment method
- Checks for pending payouts
- Minimum payout amount ($50)

### get_instructor_balance(instructor)
Calculates available balance for instructor.

**Args:**
- `instructor` - User instance

**Returns:**
- Decimal balance amount

**Calculation:**
- Total earnings from payments
- Minus platform fees (20%)
- Minus completed payouts
- Minus pending payouts

### get_course_overview(instructor)
Gets overview of all courses for an instructor.

**Args:**
- `instructor` - User instance

**Returns:**
- QuerySet of Course objects with annotations:
  - total_enrollments
  - total_revenue
  - avg_rating
  - completion_rate

### get_student_engagement(instructor)
Gets student engagement metrics for instructor's courses.

**Args:**
- `instructor` - User instance

**Returns:**
- QuerySet of Enrollment objects with:
  - Student information
  - Progress metrics
  - Last activity timestamp
  - Completion status

### get_revenue_summary(instructor)
Gets comprehensive revenue summary.

**Args:**
- `instructor` - User instance

**Returns:**
- Tuple of (earnings_dict, payouts_queryset):
  - earnings_dict: Contains total_earned, platform_fee, available_balance
  - payouts_queryset: Recent payout records

### get_lesson_dropoff(instructor, course_id)
Gets lesson-by-lesson drop-off analytics for a course.

**Args:**
- `instructor` - User instance
- `course_id` - Course ID

**Returns:**
- List of dicts with:
  - lesson_title
  - total_students
  - students_started
  - students_completed
  - completion_rate
  - dropoff_rate

## API Endpoints

### Instructor Dashboard
```http
GET /api/instructors/dashboard/
```
Get comprehensive instructor dashboard data.

**Permissions:** IsAuthenticated, IsInstructor

**Response:**
```json
{
  "courses": [
    {
      "id": 1,
      "title": "Course Title",
      "enrollments": 150,
      "avg_rating": 4.5
    }
  ],
  "students": [
    {
      "student_id": 1,
      "student_email": "student@example.com",
      "course": "Course Title",
      "completed_lessons": 8,
      "last_activity": "2024-01-15T10:30:00Z"
    }
  ],
  "revenue": {
    "total_earned": "5000.00",
    "platform_fee": "1000.00"
  },
  "payouts": [
    {
      "id": "uuid",
      "amount": "2000.00",
      "status": "completed",
      "created_at": "2024-01-10T10:00:00Z"
    }
  ]
}
```

### Instructor Profile
```http
GET /api/instructors/profile/
PUT /api/instructors/profile/
```
Get or update instructor profile.

**Permissions:** IsAuthenticated, IsInstructor

**Request Body (PUT):**
```json
{
  "bio": "Experienced instructor...",
  "headline": "Web Development Expert",
  "website": "https://example.com",
  "expertise_areas": ["Python", "Django", "Web Development"],
  "years_of_experience": 10,
  "certifications": [
    {"name": "AWS Certified", "year": 2023}
  ],
  "education": [
    {"degree": "BS Computer Science", "institution": "University", "year": 2015}
  ]
}
```

**Response:**
```json
{
  "id": "uuid",
  "user": {
    "id": 1,
    "email": "instructor@example.com"
  },
  "bio": "Experienced instructor...",
  "headline": "Web Development Expert",
  "expertise_areas": ["Python", "Django"],
  "total_courses": 5,
  "total_students": 250,
  "total_revenue": "10000.00",
  "average_rating": "4.5",
  "is_verified": true
}
```

### List Payouts
```http
GET /api/instructors/payouts/
```
List all payout requests for the instructor.

**Permissions:** IsAuthenticated, IsInstructor

**Response:**
```json
[
  {
    "id": "uuid",
    "amount": "2000.00",
    "status": "completed",
    "payment_method": "paypal",
    "requested_at": "2024-01-10T10:00:00Z",
    "completed_at": "2024-01-12T14:30:00Z"
  }
]
```

### Request Payout
```http
POST /api/instructors/payouts/request/
```
Request a new payout.

**Permissions:** IsAuthenticated, IsInstructor

**Request Body:**
```json
{
  "amount": "1000.00",
  "payment_method": "paypal",
  "payment_details": {
    "email": "instructor@paypal.com"
  }
}
```

**Response:**
```json
{
  "id": "uuid",
  "amount": "1000.00",
  "status": "pending",
  "payment_method": "paypal",
  "requested_at": "2024-01-15T10:00:00Z"
}
```

**Error Responses:**
- `400 Bad Request` - Insufficient balance or invalid data
- `403 Forbidden` - User is not an instructor

### Course Dropoff Analytics
```http
GET /api/instructors/courses/{course_id}/dropoff/
```
Get lesson-by-lesson drop-off analytics.

**Permissions:** IsAuthenticated, IsInstructor (course owner)

**Response:**
```json
{
  "course_id": 1,
  "course_title": "Course Title",
  "lessons": [
    {
      "lesson_id": 1,
      "lesson_title": "Introduction",
      "total_students": 100,
      "students_started": 100,
      "students_completed": 95,
      "completion_rate": 95.0,
      "dropoff_rate": 5.0
    }
  ]
}
```

## Integration Points

### Accounts App
- Uses User model with instructor role
- Profile extends base user profile
- Permissions: IsInstructor

### Courses App
- Retrieves instructor's courses
- Course analytics and statistics
- Course ownership validation

### Enrollments App
- Student enrollment data
- Progress tracking
- Completion statistics

### Payments App
- Revenue tracking
- Payment processing
- Platform fee calculation
- Payout processing

### Social App
- Course reviews and ratings
- Instructor rating calculation
- Student feedback

### Analytics App
- Detailed course analytics
- Student engagement metrics
- Lesson drop-off analysis

## Testing

The instructors app includes 14 comprehensive tests covering:

### Model Tests (4 tests)
- InstructorProfile creation
- InstructorPayout creation
- Statistics update
- Verification system

### Service Tests (6 tests)
- Profile management
- Payout request validation
- Balance calculation
- Revenue summary
- Course overview
- Student engagement

### API Tests (4 tests)
- Dashboard endpoint
- Profile CRUD operations
- Payout listing
- Payout request

Run tests:
```bash
python manage.py test instructors
```

Run with verbose output:
```bash
python manage.py test instructors -v 2
```

## Usage Examples

### Creating Instructor Profile
```python
from instructors.services import get_or_create_instructor_profile, update_instructor_profile
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='instructor@example.com')

# Create profile
profile = get_or_create_instructor_profile(user)

# Update profile
updated_profile = update_instructor_profile(
    user,
    bio="Experienced web developer...",
    expertise_areas=["Python", "Django", "React"],
    years_of_experience=10
)
```

### Requesting Payout
```python
from instructors.services import request_payout, get_instructor_balance

# Check balance
balance = get_instructor_balance(instructor)
print(f"Available balance: ${balance}")

# Request payout
payout = request_payout(
    instructor=instructor,
    amount=Decimal('1000.00'),
    payment_method='paypal',
    payment_details={'email': 'instructor@paypal.com'}
)
```

### Getting Course Analytics
```python
from instructors.services import get_course_overview, get_lesson_dropoff

# Get course overview
courses = get_course_overview(instructor)
for course in courses:
    print(f"{course.title}: {course.total_enrollments} students")

# Get lesson drop-off
dropoff = get_lesson_dropoff(instructor, course_id=1)
for lesson in dropoff:
    print(f"{lesson['lesson_title']}: {lesson['dropoff_rate']}% drop-off")
```

### Updating Statistics
```python
from instructors.models import InstructorProfile

profile = InstructorProfile.objects.get(user=instructor)
profile.update_statistics()
print(f"Total revenue: ${profile.total_revenue}")
```

## Revenue Sharing Model

The platform uses a revenue sharing model:

- **Instructor Share**: 80% of course price
- **Platform Fee**: 20% of course price

Example:
- Course Price: $100
- Instructor Earnings: $80
- Platform Fee: $20

Minimum payout amount: $50

## Payout Processing Workflow

1. **Request**: Instructor requests payout
2. **Validation**: System validates balance and payment details
3. **Pending**: Payout marked as pending
4. **Processing**: Admin/system processes payment
5. **Completed**: Payment sent, payout marked complete
6. **Failed**: If payment fails, payout marked failed with reason

Status flow:
```
pending → processing → completed
                    ↓
                  failed
```

## Performance Considerations

- **Denormalized Statistics**: Key metrics cached in InstructorProfile
- **Efficient Queries**: Use select_related and prefetch_related
- **Indexed Fields**: user, is_verified, ratings, student count
- **Periodic Updates**: Statistics updated via celery tasks (future)
- **Query Optimization**: Aggregations done at database level

## Security

- **Permission Checks**: IsInstructor permission on all endpoints
- **Ownership Validation**: Instructors can only access their own data
- **Payout Validation**: Prevents over-withdrawal
- **Payment Details**: Sensitive data stored in JSONField
- **Status Transitions**: Only valid status transitions allowed

## Future Enhancements

1. **Automated Payouts**: Scheduled automatic payouts
2. **Multi-currency**: Support for different currencies
3. **Tax Management**: W9/W8 forms and tax reporting
4. **Advanced Analytics**: More detailed course analytics
5. **Performance Bonuses**: Bonuses for high-rated courses
6. **Referral Program**: Instructor referral bonuses
7. **Certification Programs**: Platform-issued instructor certifications
8. **Mentorship**: Experienced instructors mentor new ones
9. **Resource Library**: Shared teaching resources
10. **Community Features**: Instructor forums and networking
