# Core App Documentation

## Overview
The core app serves as a placeholder for shared utilities, helpers, and base classes that may be used across multiple apps in the SkillStudio platform. Currently, this app is minimal and does not contain active functionality.

## Purpose
This app is reserved for future cross-cutting concerns that don't belong to any specific feature app, such as:
- Custom middleware
- Shared utility functions
- Base model classes
- Common validators
- Shared constants
- Reusable mixins
- Common exceptions

## Current Status
- **Models**: None
- **Views**: None
- **URLs**: None
- **Tests**: 0 tests
- **Services**: None

## Typical Use Cases

When the core app is needed, it typically contains:

### Custom Middleware
```python
# core/middleware.py
class RequestLoggingMiddleware:
    """Log all requests for analytics."""
    pass
```

### Shared Utilities
```python
# core/utils.py
def slugify_filename(filename):
    """Create a safe filename."""
    pass

def generate_unique_code(length=8):
    """Generate a unique alphanumeric code."""
    pass
```

### Base Models
```python
# core/models.py
from django.db import models

class TimeStampedModel(models.Model):
    """Abstract base class with created_at and updated_at."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True
```

### Validators
```python
# core/validators.py
from django.core.exceptions import ValidationError

def validate_file_size(file, max_size_mb=10):
    """Validate uploaded file size."""
    if file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"File size exceeds {max_size_mb}MB")
```

### Constants
```python
# core/constants.py
# Shared constants used across apps

PLATFORM_FEE_PERCENTAGE = 20
MAX_FILE_SIZE_MB = 100
ALLOWED_VIDEO_FORMATS = ['mp4', 'webm', 'mov']
ALLOWED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png', 'gif', 'webp']
```

### Custom Exceptions
```python
# core/exceptions.py
class BusinessLogicError(Exception):
    """Custom exception for business logic violations."""
    pass

class InsufficientBalanceError(BusinessLogicError):
    """Raised when user has insufficient balance."""
    pass
```

## Testing

The core app currently has no tests since it contains no functionality.

When functionality is added, tests should be created:
```bash
python manage.py test core
```

## Integration Points

The core app is designed to be imported by other apps when shared functionality is needed:

```python
# In other apps
from core.models import TimeStampedModel
from core.utils import slugify_filename
from core.validators import validate_file_size
from core.constants import PLATFORM_FEE_PERCENTAGE
```

## Design Principles

When adding functionality to core:

1. **Generic Only**: Only truly shared, generic functionality belongs here
2. **No Business Logic**: Business logic belongs in feature apps (courses, enrollments, etc.)
3. **Minimal Dependencies**: Core should have minimal dependencies on other apps
4. **Well Tested**: Shared utilities should be thoroughly tested
5. **Well Documented**: Document all functions and classes clearly

## When NOT to Use Core

Don't put functionality in core if:
- It's specific to one feature area (put it in that app)
- It contains business logic (belongs in services layer)
- It's only used by one or two apps (put it in those apps)
- It creates circular dependencies

## Future Additions

Potential additions when needed:
- Custom Django management commands
- Celery task base classes
- Email template helpers
- File upload utilities
- Pagination helpers
- Custom serializer fields
- API response formatters
- Cache utilities
- Logging utilities
- Metrics collection

## Current Implementation

The core app is currently scaffolded but empty:

```
core/
├── __init__.py
├── admin.py          # Empty
├── apps.py           # App configuration
├── models.py         # Empty
├── views.py          # Empty
├── tests.py          # Empty
└── migrations/       # No migrations
```

## Recommendation

The core app can remain empty until there is a clear need for shared functionality across multiple apps. When that need arises:

1. Identify truly shared, generic functionality
2. Implement in core with comprehensive tests
3. Document clearly
4. Update this README with actual functionality

For now, feature-specific code should remain in feature apps (courses, enrollments, etc.) to maintain clear separation of concerns.
