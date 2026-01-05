from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count
from django.core.exceptions import ValidationError, PermissionDenied

from .models import (
    Review, ReviewHelpful, Forum, Thread, Post, PostVote,
    LearningCircle, CircleMembership, CircleMessage,
    CircleGoal, CircleEvent, CircleResource
)
from .serializers import (
    ReviewSerializer, ForumSerializer, ThreadSerializer, PostSerializer,
    LearningCircleSerializer, LearningCircleDetailSerializer, CircleMembershipSerializer, CircleMessageSerializer,
    CircleGoalSerializer, CircleEventSerializer, CircleResourceSerializer
)
from .services import (
    submit_review, mark_review_helpful, create_thread, create_post,
    vote_post, create_learning_circle, join_learning_circle,
    leave_learning_circle, send_circle_message
)


# ===========================
# Review Views
# ===========================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_course_review(request, course_id):
    """Submit a review for a course."""
    from courses.models import Course
    
    course = get_object_or_404(Course, id=course_id)
    
    try:
        rating = request.data.get('rating')
        if rating:
            rating = int(rating)
        
        review = submit_review(
            course=course,
            user=request.user,
            rating=rating,
            title=request.data.get('title', ''),
            comment=request.data.get('comment', '')
        )
        
        serializer = ReviewSerializer(review)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    except (ValidationError, PermissionDenied) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def course_reviews(request, course_id):
    """Get all reviews for a course."""
    from courses.models import Course
    
    course = get_object_or_404(Course, id=course_id)
    reviews = Review.objects.filter(course=course, is_approved=True)
    
    serializer = ReviewSerializer(reviews, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_helpful(request, review_id):
    """Mark a review as helpful."""
    review = get_object_or_404(Review, id=review_id)
    
    try:
        mark_review_helpful(review, request.user)
        return Response({'message': 'Review marked as helpful'})
    
    except (ValidationError, PermissionDenied) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# Forum Views
# ===========================

class ForumListView(generics.ListAPIView):
    """List all forums."""
    serializer_class = ForumSerializer
    queryset = Forum.objects.filter(is_locked=False)


class ForumThreadListView(generics.ListCreateAPIView):
    """List threads in a forum."""
    serializer_class = ThreadSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        forum_id = self.kwargs['forum_id']
        return Thread.objects.filter(forum_id=forum_id)
    
    def create(self, request, *args, **kwargs):
        from django.core.exceptions import PermissionDenied
        forum = get_object_or_404(Forum, id=self.kwargs['forum_id'])
        
        try:
            thread = create_thread(
                forum=forum,
                user=request.user,
                title=request.data.get('title'),
                content=request.data.get('content'),
                tags=request.data.get('tags', [])
            )
            
            return Response(
                ThreadSerializer(thread).data,
                status=status.HTTP_201_CREATED
            )
        
        except PermissionDenied as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_403_FORBIDDEN
            )
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ThreadDetailView(generics.RetrieveAPIView):
    """Get thread details."""
    serializer_class = ThreadSerializer
    queryset = Thread.objects.all()
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Increment view count
        instance.view_count += 1
        instance.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class ThreadPostListView(generics.ListCreateAPIView):
    """List posts in a thread."""
    serializer_class = PostSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        thread_id = self.kwargs['thread_id']
        return Post.objects.filter(thread_id=thread_id, parent=None)
    
    def create(self, request, *args, **kwargs):
        thread = get_object_or_404(Thread, id=self.kwargs['thread_id'])
        
        try:
            post = create_post(
                thread=thread,
                user=request.user,
                content=request.data.get('content'),
                parent_id=request.data.get('parent_id')
            )
            
            return Response(
                PostSerializer(post).data,
                status=status.HTTP_201_CREATED
            )
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def vote_on_post(request, post_id):
    """Vote on a post."""
    post = get_object_or_404(Post, id=post_id)
    vote_type = request.data.get('vote_type')  # 'upvote' or 'downvote'
    
    if vote_type not in ['upvote', 'downvote']:
        return Response(
            {'error': 'Invalid vote type'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        vote_post(post, request.user, vote_type)
        return Response({'message': f'Post {vote_type}d successfully'})
    
    except (ValidationError, PermissionDenied) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ===========================
# Learning Circle Views
# ===========================

class LearningCircleListCreateView(generics.ListCreateAPIView):
    """List and create learning circles."""
    serializer_class = LearningCircleSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        from django.db.models import Count, Q
        
        queryset = LearningCircle.objects.exclude(status='archived').annotate(
            member_count=Count('members', filter=Q(members__status='active'))
        )
        
        # Filter by course if provided
        course_id = self.request.query_params.get('course_id')
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        # Filter public circles only
        queryset = queryset.filter(is_private=False)
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        try:
            max_members = request.data.get('max_members')
            if max_members:
                max_members = int(max_members)
            
            weekly_target = request.data.get('weekly_target_hours')
            if weekly_target:
                weekly_target = int(weekly_target)
            
            circle = create_learning_circle(
                name=request.data.get('name'),
                user=request.user,
                description=request.data.get('description', ''),
                course_id=request.data.get('course_id'),
                max_members=max_members,
                is_private=request.data.get('is_private', False),
                learning_goal=request.data.get('learning_goal', ''),
                weekly_target_hours=weekly_target
            )
            
            return Response(
                LearningCircleSerializer(circle).data,
                status=status.HTTP_201_CREATED
            )
        
        except (ValidationError, PermissionDenied) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class LearningCircleDetailView(generics.RetrieveAPIView):
    """Get learning circle details."""
    serializer_class = LearningCircleDetailSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        from django.db.models import Count, Q
        return LearningCircle.objects.annotate(
            member_count=Count('members', filter=Q(members__status='active'))
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_circle(request, circle_id):
    """Join a learning circle."""
    circle = get_object_or_404(LearningCircle, id=circle_id)
    join_code = request.data.get('join_code')
    
    try:
        membership = join_learning_circle(circle, request.user, join_code)
        
        return Response(
            CircleMembershipSerializer(membership).data,
            status=status.HTTP_201_CREATED
        )
    
    except (ValidationError, PermissionDenied) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_circle(request, circle_id):
    """Leave a learning circle."""
    circle = get_object_or_404(LearningCircle, id=circle_id)
    
    try:
        leave_learning_circle(circle, request.user)
        return Response({'message': 'Left circle successfully'})
    
    except (ValidationError, PermissionDenied) as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_circles(request):
    """Get user's learning circles."""
    from django.db.models import Count, Q
    
    memberships = CircleMembership.objects.filter(
        user=request.user,
        status='active'
    ).select_related('circle')
    
    circle_ids = [m.circle_id for m in memberships]
    circles = LearningCircle.objects.filter(id__in=circle_ids).annotate(
        member_count=Count('members', filter=Q(members__status='active'))
    )
    
    serializer = LearningCircleSerializer(circles, many=True, context={'request': request})
    
    return Response(serializer.data)


# ===========================
# Circle Chat Views
# ===========================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def circle_messages(request, circle_id):
    """Get or send messages in a circle."""
    circle = get_object_or_404(LearningCircle, id=circle_id)
    
    if request.method == 'GET':
        messages = CircleMessage.objects.filter(circle=circle)
        serializer = CircleMessageSerializer(messages, many=True)
        return Response(serializer.data)
    
    else:  # POST
        try:
            message = send_circle_message(
                circle=circle,
                user=request.user,
                message=request.data.get('message'),
                attachment=request.data.get('attachment'),
                reply_to_id=request.data.get('reply_to_id')
            )
            
            return Response(
                CircleMessageSerializer(message).data,
                status=status.HTTP_201_CREATED
            )
        
        except (ValidationError, PermissionDenied) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


# ===========================
# Circle Goals Views
# ===========================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def circle_goals(request, circle_id):
    """Get or create circle goals."""
    circle = get_object_or_404(LearningCircle, id=circle_id)
    
    if request.method == 'GET':
        goals = CircleGoal.objects.filter(circle=circle)
        serializer = CircleGoalSerializer(goals, many=True)
        return Response(serializer.data)
    
    else:  # POST
        goal = CircleGoal.objects.create(
            circle=circle,
            goal_text=request.data.get('goal_text'),
            week_start_date=request.data.get('week_start_date'),
            target_hours=request.data.get('target_hours')
        )
        
        return Response(
            CircleGoalSerializer(goal).data,
            status=status.HTTP_201_CREATED
        )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_goal_progress(request, goal_id):
    """Update goal completion status."""
    goal = get_object_or_404(CircleGoal, id=goal_id)
    
    goal.is_completed = request.data.get('is_completed', goal.is_completed)
    goal.actual_hours = request.data.get('actual_hours', goal.actual_hours)
    goal.save()
    
    return Response(CircleGoalSerializer(goal).data)


# ===========================
# Circle Events Views
# ===========================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def circle_events(request, circle_id):
    """Get or create circle events."""
    circle = get_object_or_404(LearningCircle, id=circle_id)
    
    if request.method == 'GET':
        events = CircleEvent.objects.filter(circle=circle)
        serializer = CircleEventSerializer(events, many=True)
        return Response(serializer.data)
    
    else:  # POST
        event = CircleEvent.objects.create(
            circle=circle,
            title=request.data.get('title'),
            description=request.data.get('description', ''),
            scheduled_time=request.data.get('scheduled_time'),
            meeting_link=request.data.get('meeting_link', ''),
            created_by=request.user
        )
        
        return Response(
            CircleEventSerializer(event).data,
            status=status.HTTP_201_CREATED
        )


# ===========================
# Circle Resources Views
# ===========================

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def circle_resources(request, circle_id):
    """Get or upload circle resources."""
    circle = get_object_or_404(LearningCircle, id=circle_id)
    
    if request.method == 'GET':
        resources = CircleResource.objects.filter(circle=circle)
        serializer = CircleResourceSerializer(resources, many=True)
        return Response(serializer.data)
    
    else:  # POST
        resource = CircleResource.objects.create(
            circle=circle,
            title=request.data.get('title'),
            description=request.data.get('description', ''),
            resource_type=request.data.get('resource_type'),
            file=request.data.get('file'),
            link=request.data.get('link', ''),
            uploaded_by=request.user
        )
        
        return Response(
            CircleResourceSerializer(resource).data,
            status=status.HTTP_201_CREATED
        )
