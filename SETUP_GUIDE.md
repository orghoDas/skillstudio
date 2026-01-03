# Setup & Migration Guide

## Prerequisites
- Python 3.8+
- Django 3.2+
- PostgreSQL (recommended) or SQLite
- Virtual environment activated

## Step-by-Step Setup

### 1. Install Dependencies
Ensure all requirements are installed:
```bash
pip install -r requirements.txt
```

### 2. Create Migrations
Generate migration files for the new models:

```bash
# Create migrations for adminpanel
python manage.py makemigrations adminpanel

# Create migrations for analytics
python manage.py makemigrations analytics

# Review the migrations
python manage.py showmigrations
```

### 3. Apply Migrations
Run the migrations to create database tables:

```bash
python manage.py migrate adminpanel
python manage.py migrate analytics
```

### 4. Update Main URLs
Add the new app URLs to your project's main `urls.py`:

```python
# skillstudio/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Add these lines
    path('api/adminpanel/', include('adminpanel.urls')),
    path('api/analytics/', include('analytics.urls')),
    
    # ... existing URL patterns
]
```

### 5. Create Superuser (if needed)
```bash
python manage.py createsuperuser
```

### 6. Verify Installation
Check that the apps are properly installed:

```bash
# Check installed apps
python manage.py check

# Access Django admin
python manage.py runserver
# Visit: http://localhost:8000/admin/
```

## Testing the Implementation

### Run Tests
```bash
# Test adminpanel
python manage.py test adminpanel

# Test analytics
python manage.py test analytics

# Test both
python manage.py test adminpanel analytics
```

### Manual API Testing

#### 1. Get Admin Token (if using JWT)
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@test.com", "password": "<your-password>"}'
```

#### 2. Test Admin Dashboard
```bash
curl -X GET http://localhost:8000/api/adminpanel/dashboard/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 3. Test Analytics Endpoint
```bash
curl -X GET http://localhost:8000/api/analytics/instructor/dashboard/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Optional: Populate Sample Data

### Create Sample Data Script
Create `populate_sample_data.py` in your project root:

```python
# populate_sample_data.py
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'skillstudio.settings')
django.setup()

from accounts.models import User, Profile
from courses.models import Course, Category
from enrollments.models import Enrollment
from adminpanel.models import PlatformSettings, SystemAlert
from analytics.models import UserInteraction

def populate():
    # Create sample users
    admin = User.objects.create_user(
        email='admin@skillstudio.com',
        password='admin123',
        role='admin'
    )
    
    instructor = User.objects.create_user(
        email='instructor@skillstudio.com',
        password='instructor123',
        role='instructor'
    )
    
    student = User.objects.create_user(
        email='student@skillstudio.com',
        password='student123',
        role='student'
    )
    
    # Create sample category
    category = Category.objects.create(
        name='Web Development',
        slug='web-development'
    )
    
    # Create sample course
    course = Course.objects.create(
        title='Complete Python Course',
        slug='complete-python-course',
        instructor=instructor,
        category=category,
        status='published',
        description='Learn Python from scratch'
    )
    
    # Create enrollment
    Enrollment.objects.create(
        user=student,
        course=course,
        status='active'
    )
    
    # Create platform setting
    PlatformSettings.objects.create(
        key='max_upload_size',
        value='10485760',
        description='Maximum file upload size in bytes',
        data_type='integer',
        updated_by=admin
    )
    
    # Create system alert
    SystemAlert.objects.create(
        title='Welcome to Skillstudio',
        message='Platform is now live!',
        alert_type='info',
        created_by=admin
    )
    
    # Track sample interaction
    UserInteraction.objects.create(
        user=student,
        course=course,
        action='view_course',
        metadata={'source': 'homepage'}
    )
    
    print("✅ Sample data created successfully!")
    print(f"Admin: admin@skillstudio.com / admin123")
    print(f"Instructor: instructor@skillstudio.com / instructor123")
    print(f"Student: student@skillstudio.com / student123")

if __name__ == '__main__':
    populate()
```

Run it:
```bash
python populate_sample_data.py
```

## Background Tasks Setup (Recommended)

### Install Celery
```bash
pip install celery redis
```

### Create Celery Tasks
Create `analytics/tasks.py`:

```python
from celery import shared_task
from .services import create_daily_snapshot, create_daily_platform_metrics

@shared_task
def daily_analytics_snapshot():
    """Run daily analytics snapshots"""
    create_daily_snapshot()
    create_daily_platform_metrics()
    return "Daily analytics snapshot completed"
```

### Configure Celery Beat
In `settings.py`:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'daily-analytics-snapshot': {
        'task': 'analytics.tasks.daily_analytics_snapshot',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM daily
    },
}
```

## Troubleshooting

### Issue: "No module named 'adminpanel'"
**Solution**: Ensure `adminpanel` is in `INSTALLED_APPS` in `settings.py`:
```python
INSTALLED_APPS = [
    # ...
    'adminpanel',
    'analytics',
    # ...
]
```

### Issue: Migration conflicts
**Solution**: Reset migrations if needed:
```bash
# Delete migration files (keep __init__.py)
find adminpanel/migrations -name "*.py" ! -name "__init__.py" -delete
find analytics/migrations -name "*.py" ! -name "__init__.py" -delete

# Recreate migrations
python manage.py makemigrations adminpanel analytics
python manage.py migrate
```

### Issue: Permission denied on endpoints
**Solution**: Verify user roles and permissions:
```python
# In Django shell
python manage.py shell

from accounts.models import User
user = User.objects.get(email='admin@test.com')
user.role = 'admin'
user.is_staff = True
user.save()
```

### Issue: Missing dependencies
**Solution**: Install missing packages:
```bash
pip install djangorestframework
pip install django-cors-headers
```

## Performance Optimization

### Add Database Indexes (if not auto-created)
```bash
python manage.py dbshell
```

```sql
-- Additional indexes if needed
CREATE INDEX idx_admin_actions_created ON adminpanel_adminaction(created_at DESC);
CREATE INDEX idx_user_interactions_created ON analytics_userinteraction(created_at DESC);
```

### Setup Caching
In `settings.py`:

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'skillstudio',
        'TIMEOUT': 3600,  # 1 hour
    }
}
```

## Monitoring & Logging

### Configure Logging
In `settings.py`:

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'adminpanel.log',
        },
    },
    'loggers': {
        'adminpanel': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'analytics': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

## Deployment Checklist

- [ ] All migrations applied successfully
- [ ] Tests passing (adminpanel + analytics)
- [ ] Admin superuser created
- [ ] URLs configured in main urls.py
- [ ] INSTALLED_APPS updated
- [ ] Database indexes created
- [ ] Caching configured (optional)
- [ ] Background tasks scheduled (optional)
- [ ] Logging configured
- [ ] Security settings reviewed
- [ ] CORS settings configured (if needed)
- [ ] Static files collected
- [ ] Environment variables set

## Quick Start Commands

```bash
# Complete setup in one go
python manage.py makemigrations adminpanel analytics
python manage.py migrate
python manage.py createsuperuser
python manage.py test adminpanel analytics
python manage.py runserver

# Access:
# Admin: http://localhost:8000/admin/
# API: http://localhost:8000/api/adminpanel/dashboard/
# Analytics: http://localhost:8000/api/analytics/instructor/dashboard/
```

## Support & Documentation

For detailed information, refer to:
- `adminpanel/README.md` - Complete admin panel documentation
- `analytics/README.md` - Complete analytics documentation
- `ADMINPANEL_ANALYTICS_SUMMARY.md` - Implementation summary

## Next Steps

After setup:
1. Test all endpoints using Postman or similar
2. Review and customize permissions as needed
3. Set up background tasks for daily snapshots
4. Configure monitoring and alerting
5. Review security settings for production
6. Set up proper error handling and logging
7. Configure rate limiting for API endpoints
