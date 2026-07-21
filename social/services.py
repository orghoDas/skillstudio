from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum
from django.core.exceptions import ValidationError, PermissionDenied

from .models import (
    Review, ReviewHelpful, Forum, Thread, Post, PostVote,
    LearningCircle, CircleMembership, CircleMessage,
    CircleGoal, CircleEvent, CircleResource
)


# ===========================
# Review Services
# ===========================

@transaction.atomic
def submit_review(course, user, rating, **kwargs):
    """
    Submit a course review.
    
    Args:
        course: Course instance
        user: User instance
        rating: Rating (1-5)
        **kwargs: Additional review fields
    
    Returns:
        Review instance
    
    Raises:
        ValidationError: If duplicate review or invalid rating
    """
    # Validate rating
    if rating < 1 or rating > 5:
        raise ValidationError("Rating must be between 1 and 5")
    
    if Review.objects.filter(course=course, user=user).exists():
        raise ValidationError("You have already reviewed this course")
    
    review = Review.objects.create(
        course=course,
        user=user,
        rating=rating,
        title=kwargs.get('title', ''),
        comment=kwargs.get('comment', '')
    )
    
    return review


@transaction.atomic
def mark_review_helpful(review, user):
    """
    Mark a review as helpful.
    
    Args:
        review: Review instance
        user: User instance
    
    Returns:
        ReviewHelpful instance
    """
    helpful, created = ReviewHelpful.objects.get_or_create(review=review, user=user)
    
    if created:
        review.helpful_count += 1
        review.save(update_fields=['helpful_count'])
    
    return helpful


# ===========================
# Forum Services
# ===========================

@transaction.atomic
def create_thread(forum, user, title, content, **kwargs):
    """
    Create a new discussion thread.
    
    Args:
        forum: Forum instance
        user: User instance
        title: Thread title
        content: Thread content
        **kwargs: Additional thread fields
    
    Returns:
        Thread instance
    
    Raises:
        PermissionDenied: If forum is locked
    """
    if forum.is_locked:
        raise PermissionDenied("Forum is locked")
    
    thread = Thread.objects.create(
        forum=forum,
        title=title,
        content=content,
        created_by=user,
        tags=kwargs.get('tags', [])
    )
    
    return thread


@transaction.atomic
def create_post(thread, user, content, **kwargs):
    """
    Create a post in a thread.
    
    Args:
        thread: Thread instance
        user: User instance
        content: Post content
        **kwargs: Additional post fields
    
    Returns:
        Post instance
    
    Raises:
        PermissionDenied: If thread is locked
    """
    if thread.is_locked:
        raise PermissionDenied("Thread is locked")
    
    parent = kwargs.get('parent')
    if parent is None and kwargs.get('parent_id'):
        parent = Post.objects.get(id=kwargs['parent_id'], thread=thread)

    post = Post.objects.create(
        thread=thread,
        user=user,
        content=content,
        parent=parent
    )
    
    # Update thread timestamp
    thread.updated_at = timezone.now()
    thread.save(update_fields=['updated_at'])
    
    return post


@transaction.atomic
def vote_post(post, user, vote_type):
    """
    Vote on a post (upvote/downvote).
    
    Args:
        post: Post instance
        user: User instance
        vote_type: 'upvote' or 'downvote'
    
    Returns:
        PostVote instance
    
    Raises:
        ValidationError: If invalid vote type
    """
    if vote_type not in ['upvote', 'downvote']:
        raise ValidationError("Vote type must be 'upvote' or 'downvote'")
    
    vote_value = 1 if vote_type == 'upvote' else -1
    
    vote, created = PostVote.objects.update_or_create(
        post=post,
        user=user,
        defaults={'vote': vote_value}
    )
    
    # Recalculate post upvotes
    total_votes = PostVote.objects.filter(post=post).aggregate(
        total=Sum('vote')
    )['total'] or 0
    
    post.upvotes = total_votes
    post.save(update_fields=['upvotes'])
    
    return vote


# ===========================
# Learning Circle Services
# ===========================

@transaction.atomic
def create_learning_circle(name, user, **kwargs):
    """
    Create a new learning circle.
    
    Args:
        name: Circle name
        user: User instance (creator)
        **kwargs: Additional circle fields
    
    Returns:
        LearningCircle instance
    """
    import secrets

    course = kwargs.get('course')
    if course is None and kwargs.get('course_id'):
        from courses.models import Course
        try:
            course = Course.objects.get(id=kwargs['course_id'])
        except Course.DoesNotExist:
            raise ValidationError("Course does not exist")
    
    circle = LearningCircle.objects.create(
        name=name,
        description=kwargs.get('description', ''),
        course=course,
        max_members=kwargs.get('max_members'),
        is_private=kwargs.get('is_private', False),
        join_code=secrets.token_urlsafe(8) if kwargs.get('is_private') else '',
        learning_goal=kwargs.get('learning_goal', ''),
        weekly_target_hours=kwargs.get('weekly_target_hours'),
        created_by=user
    )
    
    # Add creator as admin
    CircleMembership.objects.create(
        circle=circle,
        user=user,
        role='admin'
    )
    
    return circle


@transaction.atomic
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
    circle = LearningCircle.objects.select_for_update().get(pk=circle.pk)
    existing_membership = CircleMembership.objects.select_for_update().filter(
        circle=circle,
        user=user,
    ).first()
    
    if existing_membership and existing_membership.status == 'active':
        # If user is already a member, return the existing membership
        # This handles the case where the creator tries to "join" their own circle
        return existing_membership

    if existing_membership and existing_membership.status == 'removed':
        raise PermissionDenied("You cannot rejoin this circle")
    
    # Check if private
    if circle.is_private:
        if not join_code or join_code != circle.join_code:
            raise PermissionDenied("Invalid join code")
    
    # Check if full
    if circle.is_full():
        raise ValidationError("Circle is full")
    
    if existing_membership:
        existing_membership.status = 'active'
        existing_membership.left_at = None
        existing_membership.joined_at = timezone.now()
        existing_membership.save(update_fields=['status', 'left_at', 'joined_at'])
        return existing_membership

    membership = CircleMembership.objects.create(
        circle=circle,
        user=user,
        role='member',
        status='active',
    )
    
    return membership


@transaction.atomic
def leave_learning_circle(circle, user):
    """
    Leave a learning circle.
    
    Args:
        circle: LearningCircle instance
        user: User instance
    
    Returns:
        CircleMembership instance
    
    Raises:
        ValidationError: If user is not an active member
    """
    try:
        membership = CircleMembership.objects.select_for_update().get(
            circle=circle,
            user=user,
            status='active'
        )
    except CircleMembership.DoesNotExist:
        raise ValidationError("You are not an active member of this circle")

    if membership.role == 'admin':
        other_admin_exists = CircleMembership.objects.filter(
            circle=circle,
            role='admin',
            status='active',
        ).exclude(pk=membership.pk).exists()
        if not other_admin_exists:
            raise ValidationError("Transfer admin ownership before leaving this circle")
    
    membership.status = 'left'
    membership.left_at = timezone.now()
    membership.save(update_fields=['status', 'left_at'])
    
    return membership


@transaction.atomic
def send_circle_message(circle, user, message, **kwargs):
    """
    Send a message in a learning circle.
    
    Args:
        circle: LearningCircle instance
        user: User instance
        message: Message text
        **kwargs: Additional message fields
    
    Returns:
        CircleMessage instance
    
    Raises:
        PermissionDenied: If user is not a member
    """
    # Check membership
    if not CircleMembership.objects.filter(
        circle=circle,
        user=user,
        status='active'
    ).exists():
        raise PermissionDenied("You are not a member of this circle")

    if not message:
        raise ValidationError("Message is required")

    reply_to = kwargs.get('reply_to')
    if reply_to is None and kwargs.get('reply_to_id'):
        reply_to = CircleMessage.objects.get(id=kwargs['reply_to_id'], circle=circle)
    
    msg = CircleMessage.objects.create(
        circle=circle,
        user=user,
        message=message,
        attachment=kwargs.get('attachment'),
        reply_to=reply_to
    )
    
    return msg
