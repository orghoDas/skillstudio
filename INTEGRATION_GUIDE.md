# Integration Guide - Events & Social Apps

This guide shows how to integrate the newly completed Events and Social apps into the SkillStudio project.

## Step 1: Create Database Migrations

```bash
# Create migrations for both apps
python manage.py makemigrations events
python manage.py makemigrations social

# Apply migrations
python manage.py migrate events
python manage.py migrate social
```

## Step 2: Add to Main URL Configuration

Edit `skillstudio/urls.py` and add:

```python
from django.urls import path, include

urlpatterns = [
    # ... existing paths ...
    
    # Events app
    path('api/events/', include('events.urls')),
    
    # Social app
    path('api/social/', include('social.urls')),
]
```

## Step 3: Update INSTALLED_APPS

Verify in `skillstudio/settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'events',
    'social',
]
```

## Step 4: Run Tests

```bash
# Test events app
python manage.py test events

# Test social app
python manage.py test social

# Test both
python manage.py test events social
```

## Step 5: Create Superuser and Test Admin

```bash
# Create superuser if not exists
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Visit admin at http://localhost:8000/admin/
```

## Available Endpoints

### Events App (15 endpoints)

**Event Management:**
- GET/POST `/api/events/` - List/create events
- GET/PUT/DELETE `/api/events/<id>/` - Event details

**Registration:**
- POST `/api/events/<id>/register/` - Register for event
- POST `/api/events/<id>/cancel/` - Cancel registration
- GET `/api/events/registrations/my/` - My registrations

**Feedback:**
- POST `/api/events/<id>/feedback/submit/` - Submit feedback
- GET `/api/events/<id>/feedback/` - List feedback

**Analytics (Staff):**
- GET `/api/events/<id>/analytics/` - Event analytics
- GET `/api/events/<id>/registrations/` - Registration list
- POST `/api/events/<id>/attendance/mark/` - Mark attendance

**Resources:**
- POST `/api/events/<id>/resources/upload/` - Upload resource
- GET `/api/events/<id>/resources/` - List resources

**Discovery:**
- GET `/api/events/upcoming/` - Upcoming events
- GET `/api/events/featured/` - Featured events

### Social App (20 endpoints)

**Reviews:**
- GET `/api/social/courses/<id>/reviews/` - List reviews
- POST `/api/social/courses/<id>/reviews/submit/` - Submit review
- POST `/api/social/reviews/<id>/helpful/` - Mark helpful

**Forums:**
- GET `/api/social/forums/` - List forums
- GET/POST `/api/social/forums/<id>/threads/` - Forum threads
- GET `/api/social/threads/<id>/` - Thread details
- GET/POST `/api/social/threads/<id>/posts/` - Thread posts
- POST `/api/social/posts/<id>/vote/` - Vote on post

**Learning Circles:**
- GET/POST `/api/social/circles/` - List/create circles
- GET `/api/social/circles/<id>/` - Circle details
- POST `/api/social/circles/<id>/join/` - Join circle
- POST `/api/social/circles/<id>/leave/` - Leave circle
- GET `/api/social/circles/my-circles/` - My circles

**Circle Features:**
- GET/POST `/api/social/circles/<id>/messages/` - Chat messages
- GET/POST `/api/social/circles/<id>/goals/` - Learning goals
- PATCH `/api/social/goals/<id>/progress/` - Update progress
- GET/POST `/api/social/circles/<id>/events/` - Study sessions
- GET/POST `/api/social/circles/<id>/resources/` - Resources

## Quick Test Commands

### Test Event Creation

```bash
# Using curl (replace token with actual JWT)
curl -X POST http://localhost:8000/api/events/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Django Workshop",
    "description": "Learn Django basics",
    "event_type": "workshop",
    "start_time": "2024-02-01T10:00:00Z",
    "end_time": "2024-02-01T12:00:00Z",
    "total_seats": 30,
    "price": 0
  }'
```

### Test Learning Circle Creation

```bash
curl -X POST http://localhost:8000/api/social/circles/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Django Study Group",
    "description": "Weekly Django learning sessions",
    "max_members": 10,
    "is_private": false
  }'
```

### Test Review Submission

```bash
curl -X POST http://localhost:8000/api/social/courses/1/reviews/submit/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "rating": 5,
    "title": "Excellent Course",
    "comment": "Highly recommended!"
  }'
```

## Admin Interface Testing

1. Login to `/admin/`
2. Check these sections:
   - **Events**: Event, Event Registration, Event Feedback, Event Attendance Log, Event Resource
   - **Social**: Review, Forum, Thread, Post, Learning Circle, Circle Membership, Circle Message, Circle Goal, Circle Event, Circle Resource

## Data Model Overview

### Events App (5 models)
- **Event**: Main event entity
- **EventRegistration**: User registrations
- **EventFeedback**: Ratings and comments
- **EventAttendanceLog**: Attendance tracking
- **EventResource**: Event materials

### Social App (12 models)
- **Review**: Course reviews
- **ReviewHelpful**: Helpful votes
- **Forum**: Discussion forums
- **Thread**: Forum threads
- **Post**: Thread posts
- **PostVote**: Post votes
- **LearningCircle**: Study groups
- **CircleMembership**: Circle members
- **CircleMessage**: Group chat
- **CircleGoal**: Weekly goals
- **CircleEvent**: Study sessions
- **CircleResource**: Shared resources

## Common Issues & Solutions

### Issue: Migrations fail
**Solution**: Check that all apps are in INSTALLED_APPS and dependencies (courses, accounts) are migrated first.

```bash
python manage.py migrate courses
python manage.py migrate accounts
python manage.py migrate events
python manage.py migrate social
```

### Issue: Foreign key errors
**Solution**: Events and Social apps depend on:
- `accounts` app (User model)
- `courses` app (Course model)
- `enrollments` app (Enrollment model)

Ensure these are migrated first.

### Issue: Import errors in tests
**Solution**: Make sure all dependencies are available:
```bash
pip install -r requirements.txt
```

## Performance Optimization

### Database Indexes
Both apps include appropriate database indexes on:
- Foreign keys (event, user, course, circle)
- Status fields
- Timestamps (created_at, start_time)

### Query Optimization
- Use `select_related()` for foreign keys
- Use `prefetch_related()` for reverse relations
- Implement pagination for list views

### Caching (Future Enhancement)
Consider caching:
- Event listings
- Forum threads
- Circle member lists
- Review aggregations

## Security Considerations

### Permissions
- Events: Enrollment required for course events
- Social: Membership required for circle features
- Admin: Staff-only analytics and moderation

### Data Validation
- Rating ranges (1-5)
- Seat capacity checks
- Duplicate prevention
- Join code validation for private circles

## Next Steps

1. ✅ Run migrations
2. ✅ Add URL patterns
3. ✅ Run tests
4. ✅ Test admin interface
5. ✅ Test API endpoints
6. 📝 Create sample data for demonstration
7. 📝 Add email notifications (optional)
8. 📝 Set up real-time chat (optional)
9. 📝 Configure file upload limits
10. 📝 Set up production deployment

## Support & Documentation

For detailed information, see:
- [events/README.md](events/README.md) - Events app documentation
- [social/README.md](social/README.md) - Social app documentation
- [EVENTS_SOCIAL_SUMMARY.md](EVENTS_SOCIAL_SUMMARY.md) - Implementation summary

## Success Criteria

Both apps are production-ready when:
- ✅ All migrations applied successfully
- ✅ All tests passing
- ✅ Admin interface accessible
- ✅ API endpoints responding correctly
- ✅ Permissions working as expected
- ✅ File uploads functional (for resources)
- ✅ No console errors in browser

---

**Status**: Ready for integration and testing
**Version**: 1.0.0
**Last Updated**: 2024
