"""
Live Streaming Tests
Comprehensive tests for live streaming functionality.
"""

from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from rest_framework.test import APITestCase
from rest_framework import status
from datetime import timedelta

from accounts.models import User
from courses.models import Course, Category
from enrollments.models import Enrollment
from live.models import (
    LiveSession, SessionParticipant, LiveChatMessage, LiveQuestion,
    LivePoll, PollOption, PollVote, SessionRecording, RecordingView,
    SessionAttendance
)
from live import services


class LiveStreamingModelsTestCase(TestCase):
    """Test live streaming models."""
    
    def setUp(self):
        """Set up test data."""
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.category = Category.objects.create(name='Programming', slug='programming')
        self.course = Course.objects.create(
            instructor=self.instructor,
            category=self.category,
            title='Test Course',
            slug='test-course',
            status='published'
        )
    
    def test_live_session_creation(self):
        """Test creating a live session."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Live Session',
            description='Test description',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            platform='agora'
        )
        
        self.assertEqual(session.title, 'Test Live Session')
        self.assertEqual(session.status, 'scheduled')
        self.assertTrue(session.is_upcoming())
        self.assertFalse(session.is_live())
        self.assertFalse(session.is_past())
        self.assertEqual(session.duration_minutes(), 60)
    
    def test_session_participant_creation(self):
        """Test creating a session participant."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        participant = SessionParticipant.objects.create(
            session=session,
            user=self.student,
            status='registered'
        )
        
        self.assertEqual(participant.user, self.student)
        self.assertEqual(participant.status, 'registered')
        self.assertEqual(participant.duration_seconds, 0)
        self.assertEqual(participant.attendance_rate(), 0)
    
    def test_live_chat_message_creation(self):
        """Test creating a chat message."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        message = LiveChatMessage.objects.create(
            session=session,
            user=self.student,
            content='Hello everyone!',
            message_type='text'
        )
        
        self.assertEqual(message.content, 'Hello everyone!')
        self.assertEqual(message.message_type, 'text')
        self.assertFalse(message.is_deleted)
        self.assertFalse(message.is_pinned)
    
    def test_live_poll_creation(self):
        """Test creating a poll."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        poll = LivePoll.objects.create(
            session=session,
            created_by=self.instructor,
            question='What is your favorite language?',
            status='draft'
        )
        
        option1 = PollOption.objects.create(
            poll=poll,
            text='Python',
            order=0
        )
        option2 = PollOption.objects.create(
            poll=poll,
            text='JavaScript',
            order=1
        )
        
        self.assertEqual(poll.question, 'What is your favorite language?')
        self.assertEqual(poll.options.count(), 2)
        self.assertEqual(poll.total_votes(), 0)


class LiveStreamingServicesTestCase(TestCase):
    """Test live streaming services."""
    
    def setUp(self):
        """Set up test data."""
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.category = Category.objects.create(name='Programming', slug='programming')
        self.course = Course.objects.create(
            instructor=self.instructor,
            category=self.category,
            title='Test Course',
            slug='test-course',
            status='published'
        )
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active'
        )
    
    def test_create_live_session(self):
        """Test creating a live session via service."""
        session = services.create_live_session(
            course=self.course,
            instructor=self.instructor,
            title='Test Live Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            description='Test description'
        )
        
        self.assertIsNotNone(session)
        self.assertEqual(session.title, 'Test Live Session')
        self.assertEqual(session.status, 'scheduled')
        self.assertIsNotNone(session.stream_key)
        self.assertIsNotNone(session.channel_name)
    
    def test_create_session_validates_instructor(self):
        """Test that only course instructor can create session."""
        other_user = User.objects.create_user(
            email='other@test.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        
        with self.assertRaises(PermissionDenied):
            services.create_live_session(
                course=self.course,
                instructor=other_user,
                title='Test Session',
                scheduled_start=timezone.now() + timedelta(hours=1),
                scheduled_end=timezone.now() + timedelta(hours=2)
            )
    
    def test_start_live_session(self):
        """Test starting a live session."""
        session = services.create_live_session(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        started_session = services.start_live_session(session, self.instructor)
        
        self.assertEqual(started_session.status, 'live')
        self.assertIsNotNone(started_session.actual_start)
        self.assertTrue(started_session.is_live())
    
    def test_join_session(self):
        """Test joining a live session."""
        session = services.create_live_session(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        services.start_live_session(session, self.instructor)
        
        participant = services.join_session(session, self.student)
        
        self.assertEqual(participant.user, self.student)
        self.assertEqual(participant.status, 'joined')
        self.assertIsNotNone(participant.joined_at)
    
    def test_send_chat_message(self):
        """Test sending a chat message."""
        session = services.create_live_session(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        services.start_live_session(session, self.instructor)
        services.join_session(session, self.student)
        
        message = services.send_chat_message(
            session=session,
            user=self.student,
            content='Hello everyone!'
        )
        
        self.assertEqual(message.content, 'Hello everyone!')
        self.assertEqual(message.message_type, 'text')
        
        # Check participant stats updated
        participant = SessionParticipant.objects.get(session=session, user=self.student)
        self.assertEqual(participant.chat_messages_count, 1)
    
    def test_create_poll(self):
        """Test creating a poll."""
        session = services.create_live_session(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        poll = services.create_poll(
            session=session,
            user=self.instructor,
            question='What is your favorite language?',
            options=['Python', 'JavaScript', 'Java']
        )
        
        self.assertEqual(poll.question, 'What is your favorite language?')
        self.assertEqual(poll.options.count(), 3)
        self.assertEqual(poll.status, 'draft')
    
    def test_vote_poll(self):
        """Test voting on a poll."""
        session = services.create_live_session(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        services.start_live_session(session, self.instructor)
        services.join_session(session, self.student)
        
        poll = services.create_poll(
            session=session,
            user=self.instructor,
            question='Test poll?',
            options=['Yes', 'No']
        )
        services.start_poll(poll, self.instructor)
        
        option = poll.options.first()
        votes = services.vote_poll(
            poll=poll,
            user=self.student,
            option_ids=[option.id]
        )
        
        self.assertEqual(len(votes), 1)
        self.assertEqual(poll.total_votes(), 1)
        
        # Check option vote count
        option.refresh_from_db()
        self.assertEqual(option.votes_count, 1)


class LiveStreamingAPITestCase(APITestCase):
    """Test live streaming API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.category = Category.objects.create(name='Programming', slug='programming')
        self.course = Course.objects.create(
            instructor=self.instructor,
            category=self.category,
            title='Test Course',
            slug='test-course',
            status='published'
        )
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active'
        )
    
    def test_list_sessions(self):
        """Test listing live sessions."""
        LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2)
        )
        
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/live/sessions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle both paginated and non-paginated responses
        if isinstance(response.data, dict) and 'results' in response.data:
            self.assertGreater(len(response.data['results']), 0)
        else:
            self.assertGreater(len(response.data), 0)
    
    def test_create_session_requires_instructor(self):
        """Test that creating session requires instructor permission."""
        self.client.force_authenticate(user=self.student)
        
        data = {
            'course': self.course.id,
            'title': 'New Session',
            'description': 'Test',
            'scheduled_start': (timezone.now() + timedelta(hours=1)).isoformat(),
            'scheduled_end': (timezone.now() + timedelta(hours=2)).isoformat()
        }
        
        response = self.client.post('/api/live/sessions/create/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_create_session_as_instructor(self):
        """Test creating a session as instructor."""
        self.client.force_authenticate(user=self.instructor)
        
        data = {
            'course': self.course.id,
            'title': 'New Session',
            'description': 'Test description',
            'scheduled_start': (timezone.now() + timedelta(hours=1)).isoformat(),
            'scheduled_end': (timezone.now() + timedelta(hours=2)).isoformat(),
            'platform': 'agora',
            'enable_chat': True,
            'enable_qa': True
        }
        
        response = self.client.post('/api/live/sessions/create/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_join_session(self):
        """Test joining a live session."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            status='live'
        )
        
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/live/sessions/{session.id}/join/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('participant', response.data)
    
    def test_send_chat_message(self):
        """Test sending a chat message."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            status='live'
        )
        SessionParticipant.objects.create(
            session=session,
            user=self.student,
            status='joined'
        )
        
        self.client.force_authenticate(user=self.student)
        data = {'content': 'Hello everyone!'}
        
        response = self.client.post(
            f'/api/live/sessions/{session.id}/chat/send/',
            data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
    
    def test_ask_question(self):
        """Test asking a question."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            status='live'
        )
        SessionParticipant.objects.create(
            session=session,
            user=self.student,
            status='joined'
        )
        
        self.client.force_authenticate(user=self.student)
        data = {
            'question': 'What is the difference between lists and tuples?',
            'is_anonymous': False
        }
        
        response = self.client.post(
            f'/api/live/sessions/{session.id}/questions/ask/',
            data
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('question', response.data)
    
    def test_create_poll(self):
        """Test creating a poll."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Test Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            status='live'
        )
        
        self.client.force_authenticate(user=self.instructor)
        data = {
            'question': 'What is your favorite language?',
            'options': ['Python', 'JavaScript', 'Java'],
            'allow_multiple_answers': False
        }
        
        response = self.client.post(
            f'/api/live/sessions/{session.id}/polls/create/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('poll', response.data)
    
    def test_upcoming_sessions(self):
        """Test getting upcoming sessions for enrolled courses."""
        LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Upcoming Session',
            scheduled_start=timezone.now() + timedelta(hours=1),
            scheduled_end=timezone.now() + timedelta(hours=2),
            status='scheduled'
        )
        
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/live/upcoming/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('sessions', response.data)
    
    def test_user_session_history(self):
        """Test getting user's session history."""
        session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Past Session',
            scheduled_start=timezone.now() - timedelta(hours=2),
            scheduled_end=timezone.now() - timedelta(hours=1),
            status='ended'
        )
        SessionParticipant.objects.create(
            session=session,
            user=self.student,
            status='left'
        )
        
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/live/history/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('history', response.data)
