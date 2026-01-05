from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

User = settings.AUTH_USER_MODEL


class Review(models.Model):
    """Course reviews and ratings."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="reviews")
    
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=255, blank=True)
    comment = models.TextField(blank=True)
    
    # Helpful votes
    helpful_count = models.IntegerField(default=0)
    
    # Moderation
    is_approved = models.BooleanField(default=True)
    is_flagged = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ("user", "course")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['course', '-created_at']),
            models.Index(fields=['-helpful_count']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.course.title} ({self.rating}★)"


class ReviewHelpful(models.Model):
    """Track helpful votes on reviews."""
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('review', 'user')


class Forum(models.Model):
    """Discussion forums for courses or general topics."""
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="forums", null=True, blank=True)
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_forums')
    created_at = models.DateTimeField(default=timezone.now)
    
    # Moderation
    is_locked = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
    
    def __str__(self):
        return self.title
    
    def thread_count(self):
        return self.threads.count()
    
    def post_count(self):
        return sum(thread.posts.count() for thread in self.threads.all())


class Thread(models.Model):
    """Discussion threads within forums."""
    forum = models.ForeignKey(Forum, on_delete=models.CASCADE, related_name="threads")
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_threads')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tracking
    view_count = models.IntegerField(default=0)
    is_locked = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    is_solved = models.BooleanField(default=False)
    
    # Tags
    tags = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['-is_pinned', '-updated_at']
        indexes = [
            models.Index(fields=['forum', '-updated_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def post_count(self):
        return self.posts.count()
    
    def last_activity(self):
        last_post = self.posts.order_by('-created_at').first()
        return last_post.created_at if last_post else self.created_at


class Post(models.Model):
    """Posts/replies in discussion threads."""
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="posts")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='forum_posts')
    
    content = models.TextField()
    
    # Parent post for nested replies
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Moderation
    is_answer = models.BooleanField(default=False)  # Marked as solution/answer
    is_edited = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)
    
    # Reactions
    upvotes = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Post by {self.user.email if self.user else 'Unknown'} in {self.thread.title}"


class PostVote(models.Model):
    """Track upvotes/downvotes on posts."""
    VOTE_CHOICES = [
        (1, 'Upvote'),
        (-1, 'Downvote'),
    ]
    
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vote = models.SmallIntegerField(choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('post', 'user')


class LearningCircle(models.Model):
    """Peer learning circles/study groups."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Optional course association
    course = models.ForeignKey("courses.Course", on_delete=models.SET_NULL, null=True, blank=True, related_name='learning_circles')
    
    # Settings
    max_members = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(2)])
    is_private = models.BooleanField(default=False)
    join_code = models.CharField(max_length=20, blank=True)
    
    # Goals & Progress
    learning_goal = models.TextField(blank=True)
    weekly_target_hours = models.IntegerField(null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    # Cover image
    cover_image = models.ImageField(upload_to='circles/covers/', null=True, blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_circles")
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def get_member_count(self):
        """Get the member count - either from annotation or by querying."""
        # Check if member_count is annotated (will be an int)
        if hasattr(self, 'member_count') and isinstance(self.member_count, int):
            return self.member_count
        # Otherwise calculate it
        return self.members.filter(status='active').count()
    
    def member_count(self):
        """For backwards compatibility."""
        return self.get_member_count()
    
    def is_full(self):
        if not self.max_members:
            return False
        return self.get_member_count() >= self.max_members


class CircleMembership(models.Model):
    """Membership in learning circles."""
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
        ('member', 'Member'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('left', 'Left'),
        ('removed', 'Removed'),
    ]
    
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='circle_memberships')
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ("circle", "user")
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.email} in {self.circle.name}"


class CircleMessage(models.Model):
    """Messages in learning circle chat."""
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='circle_messages')
    
    message = models.TextField()
    
    # Attachments
    attachment = models.FileField(upload_to='circles/attachments/', null=True, blank=True)
    
    # Reply to message
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField(null=True, blank=True)
    is_edited = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Message in {self.circle.name}"


class CircleGoal(models.Model):
    """Weekly goals for learning circles."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('missed', 'Missed'),
    ]
    
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name='goals')
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Timeline
    start_date = models.DateField()
    end_date = models.DateField()
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.title} - {self.circle.name}"


class CircleEvent(models.Model):
    """Study sessions/meetings for learning circles."""
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name='circle_events')
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    scheduled_at = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)
    
    # Meeting link
    meeting_link = models.URLField(blank=True)
    
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['scheduled_at']
    
    def __str__(self):
        return f"{self.title} - {self.circle.name}"


class CircleResource(models.Model):
    """Shared resources in learning circles."""
    RESOURCE_TYPES = [
        ('link', 'Link'),
        ('file', 'File'),
        ('note', 'Note'),
    ]
    
    circle = models.ForeignKey(LearningCircle, on_delete=models.CASCADE, related_name='resources')
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    
    # Content
    url = models.URLField(blank=True)
    file = models.FileField(upload_to='circles/resources/', null=True, blank=True)
    note_content = models.TextField(blank=True)
    
    shared_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.circle.name}"
