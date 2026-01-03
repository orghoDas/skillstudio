# Service Layer Pattern Alignment

## Overview
After reviewing the existing apps (courses, enrollments, assessments, exams), I've aligned the Events and Social apps to follow the established service layer patterns.

## Key Patterns Learned & Applied

### 1. Exception Handling

**Before (Events/Social - Initial):**
```python
def register_for_event(event, user):
    if event.is_full():
        raise ValueError("Event is full")
    if not enrollment_exists:
        raise ValueError("Must be enrolled")
```

**After (Aligned with existing apps):**
```python
from django.core.exceptions import ValidationError, PermissionDenied

@transaction.atomic
def register_for_event(event, user):
    if event.is_full():
        raise ValidationError("Event is full")  # Data validation issues
    if not enrollment_exists:
        raise PermissionDenied("Must be enrolled")  # Access control issues
```

**Pattern Source:** `assessments/services.py`, `enrollments/services.py`
- Use `ValidationError` for data validation failures (full capacity, invalid input)
- Use `PermissionDenied` for authorization/access control issues
- Avoid generic `ValueError` or `Exception`

### 2. Transaction Management

**Before:**
```python
def cancel_event_registration(registration):
    registration.status = 'cancelled'
    registration.save()
```

**After:**
```python
from django.db import transaction

@transaction.atomic
def cancel_event_registration(registration):
    registration.status = 'cancelled'
    registration.save(update_fields=['status', 'cancelled_at'])
```

**Pattern Source:** `assessments/services.py` (submit_quiz_attempt), `exams/services.py`
- Use `@transaction.atomic` decorator for data consistency
- Ensures all-or-nothing operations (rollback on errors)
- Particularly important for multi-step operations

### 3. Optimized Database Updates

**Before:**
```python
def mark_review_helpful(review, user):
    review.helpful_count += 1
    review.save()  # Updates all fields
```

**After:**
```python
def mark_review_helpful(review, user):
    review.helpful_count += 1
    review.save(update_fields=['helpful_count'])  # Only updates specific fields
```

**Pattern Source:** `enrollments/services.py` (check_and_complete_course)
- Use `update_fields` parameter in `save()` for better performance
- Only writes changed fields to database
- Prevents race conditions on concurrent updates

### 4. Input Validation

**Before:**
```python
def submit_event_feedback(event, user, rating):
    feedback = EventFeedback.objects.create(
        rating=rating  # No validation
    )
```

**After:**
```python
def submit_event_feedback(event, user, rating):
    # Validate rating
    if rating < 1 or rating > 5:
        raise ValidationError("Rating must be between 1 and 5")
    
    feedback = EventFeedback.objects.create(rating=rating)
```

**Pattern Source:** `assessments/services.py` (grade_submission)
- Validate inputs before database operations
- Provide clear error messages
- Check business rules (ranges, formats, etc.)

### 5. Comprehensive Docstrings

**Before:**
```python
def join_learning_circle(circle, user):
    """Join a learning circle."""
```

**After:**
```python
def join_learning_circle(circle, user, join_code=None):
    """
    Join a learning circle.
    
    Args:
        circle: LearningCircle instance
        user: User instance
        join_code: Optional join code for private circles
    
    Returns:
        CircleMembership instance
    
    Raises:
        PermissionDenied: If join code is invalid
        ValidationError: If circle is full or user is already a member
    """
```

**Pattern Source:** All existing service files
- Document parameters with types
- Document return values
- Document exceptions that can be raised
- Explain purpose and business logic

### 6. Error Handling with get_or_create

**Before:**
```python
def leave_learning_circle(circle, user):
    membership = CircleMembership.objects.get(...)  # May raise DoesNotExist
```

**After:**
```python
def leave_learning_circle(circle, user):
    try:
        membership = CircleMembership.objects.get(...)
    except CircleMembership.DoesNotExist:
        raise ValidationError("You are not an active member of this circle")
```

**Pattern Source:** Common Django pattern, seen in exams/assessments
- Catch DoesNotExist exceptions
- Convert to meaningful ValidationError
- Provide user-friendly error messages

## Comparison with Existing Apps

### Courses App (`courses/services.py`)
**Pattern:** Validation functions
```python
def validate_course_for_submission(course: Course):
    if not modules.exists():
        raise ValidationError("Course must have at least one module.")
```
**Applied to:** Events - validating event requirements, Social - validating review/forum permissions

### Enrollments App (`enrollments/services.py`)
**Pattern:** Status tracking with update_fields
```python
enrollment.status = 'completed'
enrollment.is_completed = True
enrollment.save(update_fields=['status', 'is_completed', 'completed_at'])
```
**Applied to:** Events - registration status updates, Social - membership status changes

### Assessments App (`assessments/services.py`)
**Pattern:** @transaction.atomic for multi-step operations
```python
@transaction.atomic
def submit_quiz_attempt(attempt, answers):
    # Calculate score
    # Update attempt
    # Multiple database operations in transaction
```
**Applied to:** Events - event registration (check capacity + create record), Social - post voting (update vote + recalculate total)

### Exams App (`exams/services.py`)
**Pattern:** Complex validation with clear error messages
```python
if existing_attempts >= exam.max_attempts:
    raise ValueError(f"Maximum attempts ({exam.max_attempts}) exceeded")
```
**Applied to:** Events - seat capacity checks, Social - circle membership limits

## Changes Summary

### Events App Services (`events/services.py`)
- ✅ Added `@transaction.atomic` to 4 service functions
- ✅ Replaced 8 `ValueError` with `ValidationError`/`PermissionDenied`
- ✅ Added `update_fields` to 4 `save()` calls
- ✅ Added rating validation (1-5 range)
- ✅ Fixed field reference bug (`scheduled_for` → `start_time`)
- ✅ Fixed import for `Q` object
- ✅ Enhanced all docstrings with Args/Returns/Raises

### Social App Services (`social/services.py`)
- ✅ Added `@transaction.atomic` to 8 service functions
- ✅ Replaced 7 `ValueError` with `ValidationError`/`PermissionDenied`
- ✅ Added `update_fields` to 6 `save()` calls
- ✅ Added rating validation (1-5 range)
- ✅ Added vote type validation
- ✅ Fixed `models.Sum` → imported `Sum`
- ✅ Added error handling for `CircleMembership.DoesNotExist`
- ✅ Enhanced all docstrings with Args/Returns/Raises

## Benefits of Alignment

### 1. Consistency
- Developers familiar with one app can easily work on another
- Predictable error handling across the platform
- Uniform code review standards

### 2. Reliability
- Transaction atomicity prevents partial updates
- Proper exception types for better error handling
- Input validation prevents invalid data

### 3. Performance
- `update_fields` reduces database write overhead
- Transaction management improves concurrency
- Optimized query patterns

### 4. Maintainability
- Clear docstrings aid future development
- Consistent patterns reduce cognitive load
- Easy to test and debug

## Testing Implications

The improved service layer makes testing easier:

```python
# Clear exception types for testing
def test_cannot_join_full_circle(self):
    # Fill circle to capacity
    ...
    
    with self.assertRaises(ValidationError) as cm:
        join_learning_circle(circle, new_user)
    
    self.assertEqual(str(cm.exception), "Circle is full")

# Transaction rollback on errors
def test_registration_atomicity(self):
    # If payment fails, registration should not be created
    with self.assertRaises(ValidationError):
        register_for_event(event, user)
    
    # No partial registration should exist
    self.assertFalse(EventRegistration.objects.filter(user=user).exists())
```

## Next Steps

1. ✅ Service layer aligned with existing patterns
2. 🔄 Review views for consistent exception handling
3. 🔄 Ensure tests cover all ValidationError/PermissionDenied cases
4. 🔄 Add integration tests for transaction atomicity
5. 🔄 Document API error responses for each exception type

---

**Conclusion:** Both Events and Social apps now follow the established service layer patterns from the existing SkillStudio apps, ensuring consistency, reliability, and maintainability across the entire platform.
