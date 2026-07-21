from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import (
    Review, ReviewHelpful, Forum, Thread, Post, PostVote,
    LearningCircle, CircleMembership, CircleMessage,
    CircleGoal, CircleEvent, CircleResource
)
from courses.models import Course
from enrollments.models import Enrollment

User = get_user_model()


def response_items(response):
    if isinstance(response.data, dict):
        return response.data.get('results', response.data)
    return response.data


class ReviewModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test Description',
            instructor=self.user
        )
        
        self.review = Review.objects.create(
            course=self.course,
            user=self.user,
            rating=5,
            title='Great Course',
            comment='Highly recommended'
        )
    
    def test_review_creation(self):
        """Test review is created properly."""
        self.assertEqual(self.review.rating, 5)
        self.assertEqual(self.review.title, 'Great Course')
        self.assertEqual(self.review.helpful_count, 0)
    
    def test_helpful_count(self):
        """Test helpful count increments."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@test.com',
            password='pass123'
        )
        
        ReviewHelpful.objects.create(review=self.review, user=other_user)
        self.review.helpful_count += 1
        self.review.save()
        
        self.assertEqual(self.review.helpful_count, 1)


class ReviewAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test Description',
            instructor=self.user
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_submit_review(self):
        """Test submitting a course review."""
        url = f'/api/social/courses/{self.course.id}/reviews/submit/'
        data = {
            'rating': 5,
            'title': 'Great Course',
            'comment': 'Very informative'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Review.objects.filter(
                course=self.course,
                user=self.user
            ).exists()
        )
    
    def test_cannot_submit_duplicate_review(self):
        """Test user cannot submit multiple reviews for same course."""
        Review.objects.create(
            course=self.course,
            user=self.user,
            rating=5
        )
        
        url = f'/api/social/courses/{self.course.id}/reviews/submit/'
        data = {'rating': 4}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_course_reviews(self):
        """Test listing course reviews."""
        Review.objects.create(
            course=self.course,
            user=self.user,
            rating=5
        )
        
        url = f'/api/social/courses/{self.course.id}/reviews/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_items(response)), 1)


class ForumThreadTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test Description',
            instructor=self.user
        )
        
        self.forum = Forum.objects.create(
            title='Test Forum',
            description='Test Description',
            course=self.course
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_create_thread(self):
        """Test creating a discussion thread."""
        url = f'/api/social/forums/{self.forum.id}/threads/'
        data = {
            'title': 'Test Thread',
            'content': 'This is a test thread',
            'tags': ['python', 'django']
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Thread.objects.filter(
                forum=self.forum,
                title='Test Thread'
            ).exists()
        )
    
    def test_list_threads(self):
        """Test listing threads in a forum."""
        Thread.objects.create(
            forum=self.forum,
            title='Test Thread',
            content='Test Content',
            created_by=self.user
        )
        
        url = f'/api/social/forums/{self.forum.id}/threads/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_items(response)), 1)
    
    def test_view_count_increments(self):
        """Test thread view count increments."""
        thread = Thread.objects.create(
            forum=self.forum,
            title='Test Thread',
            content='Test Content',
            created_by=self.user
        )
        
        url = f'/api/social/threads/{thread.id}/'
        response = self.client.get(url)
        
        thread.refresh_from_db()
        self.assertEqual(thread.view_count, 1)


class PostVoteTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test Description',
            instructor=self.user
        )
        
        self.forum = Forum.objects.create(
            title='Test Forum',
            course=self.course
        )
        
        self.thread = Thread.objects.create(
            forum=self.forum,
            title='Test Thread',
            content='Test Content',
            created_by=self.user
        )
        
        self.post = Post.objects.create(
            thread=self.thread,
            user=self.user,
            content='Test post content'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_upvote_post(self):
        """Test upvoting a post."""
        url = f'/api/social/posts/{self.post.id}/vote/'
        data = {'vote_type': 'upvote'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.upvotes, 1)
    
    def test_downvote_post(self):
        """Test downvoting a post."""
        url = f'/api/social/posts/{self.post.id}/vote/'
        data = {'vote_type': 'downvote'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.upvotes, -1)


class LearningCircleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test Description',
            instructor=self.user
        )
        
        self.circle = LearningCircle.objects.create(
            name='Test Circle',
            description='Test Description',
            course=self.course,
            max_members=10,
            created_by=self.user
        )
    
    def test_circle_creation(self):
        """Test learning circle is created properly."""
        self.assertEqual(self.circle.name, 'Test Circle')
        self.assertEqual(self.circle.max_members, 10)
    
    def test_is_full(self):
        """Test is_full method."""
        self.assertFalse(self.circle.is_full())
        
        # Add max members
        for i in range(10):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@test.com',
                password='pass123'
            )
            CircleMembership.objects.create(
                circle=self.circle,
                user=user,
                status='active'
            )
        
        self.assertTrue(self.circle.is_full())


class LearningCircleAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test Description',
            instructor=self.user
        )
        
        self.circle = LearningCircle.objects.create(
            name='Test Circle',
            description='Test Description',
            course=self.course,
            max_members=10,
            is_private=False,
            created_by=self.user
        )
        
        # Add creator as admin
        CircleMembership.objects.create(
            circle=self.circle,
            user=self.user,
            role='admin',
            status='active'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_list_circles(self):
        """Test listing learning circles."""
        url = '/api/social/circles/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response_items(response)), 1)
    
    def test_create_circle(self):
        """Test creating a learning circle."""
        url = '/api/social/circles/'
        data = {
            'name': 'New Circle',
            'description': 'New Description',
            'course_id': self.course.id,
            'max_members': 15
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            LearningCircle.objects.filter(name='New Circle').exists()
        )
    
    def test_join_circle(self):
        """Test joining a learning circle."""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@test.com',
            password='pass123'
        )
        self.client.force_authenticate(user=other_user)
        
        url = f'/api/social/circles/{self.circle.id}/join/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            CircleMembership.objects.filter(
                circle=self.circle,
                user=other_user
            ).exists()
        )
    
    def test_leave_circle(self):
        """Test leaving a learning circle."""
        other_admin = User.objects.create_user(
            username='circleadmin',
            email='circleadmin@test.com',
            password='pass123'
        )
        CircleMembership.objects.create(
            circle=self.circle,
            user=other_admin,
            role='admin',
            status='active'
        )

        url = f'/api/social/circles/{self.circle.id}/leave/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        membership = CircleMembership.objects.get(
            circle=self.circle,
            user=self.user
        )
        self.assertEqual(membership.status, 'left')
    
    def test_send_message(self):
        """Test sending a message in circle."""
        url = f'/api/social/circles/{self.circle.id}/messages/'
        data = {'message': 'Hello everyone!'}
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            CircleMessage.objects.filter(
                circle=self.circle,
                user=self.user
            ).exists()
        )


class LearningCircleAccessControlAPITest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.creator = User.objects.create_user(
            username='creator',
            email='creator@test.com',
            password='testpass123'
        )
        self.member = User.objects.create_user(
            username='member',
            email='member@test.com',
            password='testpass123'
        )
        self.outsider = User.objects.create_user(
            username='outsider',
            email='outsider@test.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Private Circle Course',
            description='Private Description',
            instructor=self.creator
        )
        self.private_circle = LearningCircle.objects.create(
            name='Private Circle',
            description='Private Description',
            course=self.course,
            is_private=True,
            join_code='super-secret',
            created_by=self.creator
        )
        CircleMembership.objects.create(
            circle=self.private_circle,
            user=self.creator,
            role='admin',
            status='active'
        )
        CircleMembership.objects.create(
            circle=self.private_circle,
            user=self.member,
            role='member',
            status='active'
        )
        CircleMessage.objects.create(
            circle=self.private_circle,
            user=self.member,
            message='members only'
        )

    def test_private_circle_detail_hidden_from_non_member(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(f'/api/social/circles/{self.private_circle.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_private_child_resources_hidden_from_non_member(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(f'/api/social/circles/{self.private_circle.id}/messages/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_read_private_circle_without_join_code_leak(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.get(f'/api/social/circles/{self.private_circle.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('join_code', response.data)

    def test_list_does_not_leak_join_code_for_visible_private_circle(self):
        self.client.force_authenticate(user=self.member)

        response = self.client.get('/api/social/circles/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        circles = response_items(response)
        self.assertEqual(len(circles), 1)
        self.assertNotIn('join_code', circles[0])

    def test_join_code_required_for_private_circle(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.post(f'/api/social/circles/{self.private_circle.id}/join/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        response = self.client.post(
            f'/api/social/circles/{self.private_circle.id}/join/',
            {'join_code': 'super-secret'}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_rejoin_reactivates_existing_membership(self):
        membership = CircleMembership.objects.get(circle=self.private_circle, user=self.member)
        membership.status = 'left'
        membership.save(update_fields=['status'])
        self.client.force_authenticate(user=self.member)

        response = self.client.post(
            f'/api/social/circles/{self.private_circle.id}/join/',
            {'join_code': 'super-secret'}
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        membership.refresh_from_db()
        self.assertEqual(membership.status, 'active')
        self.assertEqual(
            CircleMembership.objects.filter(circle=self.private_circle, user=self.member).count(),
            1
        )

    def test_legacy_schema_fields_create_goal_event_and_resource(self):
        self.client.force_authenticate(user=self.member)

        goal_response = self.client.post(
            f'/api/social/circles/{self.private_circle.id}/goals/',
            {
                'goal_text': 'Study together',
                'week_start_date': '2026-07-21',
            }
        )
        self.assertEqual(goal_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CircleGoal.objects.filter(title='Study together').exists())

        event_response = self.client.post(
            f'/api/social/circles/{self.private_circle.id}/events/',
            {
                'title': 'Study call',
                'scheduled_time': '2026-07-22T10:00:00Z',
            }
        )
        self.assertEqual(event_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CircleEvent.objects.filter(title='Study call').exists())

        resource_response = self.client.post(
            f'/api/social/circles/{self.private_circle.id}/resources/',
            {
                'title': 'Docs',
                'resource_type': 'link',
                'link': 'https://example.com/docs',
            }
        )
        self.assertEqual(resource_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            CircleResource.objects.filter(
                title='Docs',
                url='https://example.com/docs',
                shared_by=self.member,
            ).exists()
        )
