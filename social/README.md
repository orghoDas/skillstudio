# Social App

The Social app provides comprehensive community features for the SkillStudio platform, including course reviews, discussion forums, and peer learning circles.

## Features

### 1. Course Reviews & Ratings
- Submit course reviews with ratings (1-5 stars)
- Write detailed review comments
- Mark reviews as helpful
- View aggregated course ratings
- Review moderation (hide inappropriate reviews)

### 2. Discussion Forums
- Course-specific and general forums
- Create and manage discussion threads
- Nested replies and conversations
- Thread tagging for organization
- Post voting (upvotes/downvotes)
- Mark answers in Q&A threads
- Pin important threads
- Lock threads to prevent further replies
- Track view counts

### 3. Peer Learning Circles
- Create and join study groups
- Public and private circles (with join codes)
- Member capacity management
- Role-based access (admin, moderator, member)
- Group chat with threaded messages
- File attachments in messages
- Set weekly learning goals
- Track progress hours
- Schedule study sessions/meetings
- Share learning resources
- Course-based or independent circles

## Models

### Reviews

#### Review
Course reviews with ratings and helpful tracking.

**Key Fields:**
- `course`, `user`: Review mapping
- `rating`: 1-5 star rating
- `title`, `comment`: Review content
- `helpful_count`: Helpful votes
- `is_hidden`: Moderation flag

#### ReviewHelpful
Tracks which users found a review helpful.

### Forums

#### Forum
Discussion forum container.

**Key Fields:**
- `name`, `description`: Forum information
- `course`: Associated course (optional)
- `thread_count`, `post_count`: Statistics
- `is_locked`: Prevent new threads

#### Thread
Discussion thread within a forum.

**Key Fields:**
- `forum`: Parent forum
- `title`, `content`: Thread content
- `created_by`: Thread author
- `tags`: List of tags
- `is_pinned`, `is_locked`: Moderation
- `is_solved`: Mark resolved Q&A
- `view_count`: View tracking

#### Post
Reply in a thread (supports nesting).

**Key Fields:**
- `thread`: Parent thread
- `user`: Post author
- `content`: Post text
- `parent`: Parent post (for replies)
- `upvotes`: Vote count
- `is_answer`: Mark as answer

#### PostVote
Tracks upvotes/downvotes on posts.

**Key Fields:**
- `post`, `user`: Vote mapping
- `vote`: +1 or -1

### Learning Circles

#### LearningCircle
Peer learning group.

**Key Fields:**
- `name`, `description`: Circle information
- `course`: Associated course (optional)
- `created_by`: Circle creator
- `max_members`: Capacity limit
- `is_private`: Privacy setting
- `join_code`: Access code for private circles
- `learning_goal`: Group objective
- `weekly_target_hours`: Goal hours
- `is_archived`: Archive inactive circles

**Methods:**
- `is_full()`: Check if at capacity

#### CircleMembership
User membership in a circle.

**Key Fields:**
- `circle`, `user`: Membership mapping
- `role`: admin/moderator/member
- `status`: active/left
- `joined_at`, `left_at`: Timestamps

#### CircleMessage
Chat messages within a circle.

**Key Fields:**
- `circle`, `user`: Message mapping
- `message`: Message text
- `attachment`: File attachment (optional)
- `reply_to`: Threaded replies

#### CircleGoal
Weekly learning goals for circles.

**Key Fields:**
- `circle`: Parent circle
- `goal_text`: Goal description
- `week_start_date`: Week tracking
- `target_hours`, `actual_hours`: Progress
- `is_completed`: Completion flag

#### CircleEvent
Study sessions and meetings.

**Key Fields:**
- `circle`: Parent circle
- `title`, `description`: Event details
- `scheduled_time`: When scheduled
- `meeting_link`: Video call link
- `created_by`: Event creator

#### CircleResource
Shared learning resources.

**Key Fields:**
- `circle`: Parent circle
- `title`, `description`: Resource info
- `resource_type`: link/pdf/video/other
- `file`: Uploaded file (optional)
- `link`: External URL (optional)
- `uploaded_by`: Uploader

## API Endpoints

### Reviews
```
GET    /api/social/courses/<id>/reviews/           # List course reviews
POST   /api/social/courses/<id>/reviews/submit/    # Submit review
POST   /api/social/reviews/<id>/helpful/           # Mark helpful
```

### Forums
```
GET    /api/social/forums/                         # List forums
GET    /api/social/forums/<id>/threads/            # List threads
POST   /api/social/forums/<id>/threads/            # Create thread
GET    /api/social/threads/<id>/                   # Thread details
GET    /api/social/threads/<id>/posts/             # List posts
POST   /api/social/threads/<id>/posts/             # Create post
POST   /api/social/posts/<id>/vote/                # Vote on post
```

### Learning Circles
```
GET    /api/social/circles/                        # List circles
POST   /api/social/circles/                        # Create circle
GET    /api/social/circles/<id>/                   # Circle details
POST   /api/social/circles/<id>/join/              # Join circle
POST   /api/social/circles/<id>/leave/             # Leave circle
GET    /api/social/circles/my-circles/             # My circles
```

### Circle Features
```
GET    /api/social/circles/<id>/messages/          # List messages
POST   /api/social/circles/<id>/messages/          # Send message
GET    /api/social/circles/<id>/goals/             # List goals
POST   /api/social/circles/<id>/goals/             # Create goal
PATCH  /api/social/goals/<id>/progress/            # Update progress
GET    /api/social/circles/<id>/events/            # List events
POST   /api/social/circles/<id>/events/            # Create event
GET    /api/social/circles/<id>/resources/         # List resources
POST   /api/social/circles/<id>/resources/         # Upload resource
```

## Usage Examples

### Submit Course Review
```python
POST /api/social/courses/1/reviews/submit/
{
    "rating": 5,
    "title": "Excellent Course",
    "comment": "This course exceeded my expectations. Clear explanations and great examples."
}
```

### Create Discussion Thread
```python
POST /api/social/forums/1/threads/
{
    "title": "How to implement authentication?",
    "content": "I'm struggling with Django authentication. Any tips?",
    "tags": ["django", "authentication", "help"]
}
```

### Vote on Post
```python
POST /api/social/posts/5/vote/
{
    "vote_type": "upvote"  # or "downvote"
}
```

### Create Learning Circle
```python
POST /api/social/circles/
{
    "name": "Django Study Group",
    "description": "Weekly meetings to learn Django together",
    "course_id": 1,
    "max_members": 10,
    "is_private": false,
    "learning_goal": "Complete Django tutorial and build a project",
    "weekly_target_hours": 5
}
```

### Join Private Circle
```python
POST /api/social/circles/2/join/
{
    "join_code": "abc123xyz"
}
```

### Send Circle Message
```python
POST /api/social/circles/1/messages/
{
    "message": "Hey everyone! Ready for our study session tomorrow?",
    "reply_to_id": 5  # Optional - for threaded replies
}
```

### Create Weekly Goal
```python
POST /api/social/circles/1/goals/
{
    "goal_text": "Complete chapters 3-5 of the course",
    "week_start_date": "2024-02-01",
    "target_hours": 8
}
```

### Update Goal Progress
```python
PATCH /api/social/goals/1/progress/
{
    "actual_hours": 6,
    "is_completed": true
}
```

### Schedule Study Session
```python
POST /api/social/circles/1/events/
{
    "title": "Weekly Study Session",
    "description": "Review chapters 3-5 and work on exercises",
    "scheduled_time": "2024-02-05T18:00:00Z",
    "meeting_link": "https://meet.example.com/abc123"
}
```

## Permissions

### Reviews
- **Public**: View reviews
- **Authenticated**: Submit reviews, mark helpful
- **Staff**: Hide inappropriate reviews

### Forums
- **Public**: View forums and threads
- **Authenticated**: Create threads, post replies, vote
- **Staff**: Pin/lock threads, moderate posts

### Learning Circles
- **Authenticated**: Create circles, join public circles
- **Circle Members**: View messages, participate in chat
- **Circle Admins**: Manage members, create events/goals
- **Private Circles**: Require join code

## Business Logic (services.py)

### Key Functions

#### `submit_review(course, user, rating, **kwargs)`
Submits a course review:
- Prevents duplicate reviews
- Validates rating range
- Creates review record

#### `mark_review_helpful(review, user)`
Marks a review as helpful:
- Prevents duplicate votes
- Increments helpful count

#### `create_thread(forum, user, title, content, **kwargs)`
Creates a discussion thread:
- Checks if forum is locked
- Handles tags
- Creates thread record

#### `create_post(thread, user, content, **kwargs)`
Creates a post in a thread:
- Checks if thread is locked
- Supports nested replies
- Updates thread timestamp

#### `vote_post(post, user, vote_type)`
Votes on a post:
- Handles upvotes (+1) and downvotes (-1)
- Prevents duplicate votes (updates existing)
- Recalculates post vote total

#### `create_learning_circle(name, user, **kwargs)`
Creates a learning circle:
- Generates join code for private circles
- Adds creator as admin
- Validates max_members

#### `join_learning_circle(circle, user, join_code=None)`
Joins a learning circle:
- Validates join code for private circles
- Checks capacity
- Prevents duplicate membership
- Creates membership record

#### `leave_learning_circle(circle, user)`
Leaves a learning circle:
- Updates membership status
- Records leave timestamp

#### `send_circle_message(circle, user, message, **kwargs)`
Sends a message in a circle:
- Validates membership
- Supports attachments
- Handles threaded replies

## Admin Interface

The Social admin provides:
- Review management and moderation
- Forum and thread administration
- Post moderation with vote tracking
- Learning circle overview
- Membership management
- Message monitoring
- Goal and event tracking
- Resource management

## Testing

Run tests:
```bash
python manage.py test social
```

Test coverage includes:
- Review submission and helpful voting
- Thread creation and viewing
- Post voting system
- Circle creation and membership
- Message sending
- Permission checks
- Duplicate prevention

## Integration with Other Apps

### Courses App
- Reviews linked to courses
- Forums can be course-specific
- Learning circles can focus on specific courses

### Enrollments App
- Only enrolled students can participate in course forums
- Circle recommendations based on enrollments

## Future Enhancements

- [ ] Notifications for thread replies
- [ ] Email digests for circle activity
- [ ] Badge system for helpful community members
- [ ] Advanced search in forums
- [ ] Thread subscription/following
- [ ] Resource voting/rating
- [ ] Calendar integration for circle events
- [ ] Video chat integration
- [ ] AI-powered content moderation
