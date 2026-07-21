"""
Live Streaming Tests
Comprehensive tests for live streaming functionality.
"""

from django.test import TestCase
from django.test import TransactionTestCase
from django.test import override_settings
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
import jwt
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import AccessToken
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
from live.consumers import LiveStreamConsumer


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


class LiveAccessControlAPITestCase(APITestCase):
    """Regression tests for live-session object access containment."""

    def setUp(self):
        self.instructor = User.objects.create_user(
            email='live-owner@test.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        self.other_instructor = User.objects.create_user(
            email='live-other-instructor@test.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            email='live-student@test.com',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.outsider = User.objects.create_user(
            email='live-outsider@test.com',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.category = Category.objects.create(name='Live Programming', slug='live-programming')
        self.course = Course.objects.create(
            instructor=self.instructor,
            category=self.category,
            title='Live Course',
            slug='live-course',
            status='published'
        )
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active'
        )
        self.session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Private Live Session',
            scheduled_start=timezone.now() - timedelta(minutes=5),
            scheduled_end=timezone.now() + timedelta(hours=1),
            status='live',
            platform='zoom',
            meeting_link='https://example.com/secret-meeting',
            meeting_id='secret-id',
            meeting_password='secret-password',
            requires_enrollment=True,
            is_public=False,
        )

    def test_unenrolled_user_cannot_read_private_session(self):
        self.client.force_authenticate(user=self.outsider)

        response = self.client.get(f'/api/live/sessions/{self.session.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_enrolled_student_can_read_session_without_meeting_credentials(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get(f'/api/live/sessions/{self.session.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('meeting_link', response.data)
        self.assertNotIn('meeting_id', response.data)
        self.assertNotIn('meeting_password', response.data)

    def test_join_response_returns_meeting_credentials_to_authorized_student(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.post(f'/api/live/sessions/{self.session.id}/join/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['session']['meeting_link'], self.session.meeting_link)
        self.assertEqual(response.data['session']['meeting_password'], self.session.meeting_password)

    def test_unrelated_instructor_cannot_manage_session(self):
        self.client.force_authenticate(user=self.other_instructor)

        response = self.client.post(f'/api/live/sessions/{self.session.id}/streaming/start/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_enrolled_student_must_join_before_reading_interactions(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get(f'/api/live/sessions/{self.session.id}/chat/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.post(f'/api/live/sessions/{self.session.id}/join/')
        response = self.client.get(f'/api/live/sessions/{self.session.id}/chat/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @override_settings(
        LIVEKIT_ENABLED=True,
        LIVEKIT_URL='wss://skillstudio-test.livekit.cloud',
        LIVEKIT_API_KEY='test-livekit-key',
        LIVEKIT_API_SECRET='test-livekit-secret',
        LIVEKIT_TOKEN_TTL_SECONDS=900,
    )
    def test_livekit_join_returns_subscribe_only_student_token(self):
        self.session.platform = 'livekit'
        self.session.save(update_fields=['platform'])
        self.client.force_authenticate(user=self.student)

        response = self.client.post(f'/api/live/sessions/{self.session.id}/join/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        provider_payload = response.data['provider']
        self.assertEqual(provider_payload['provider'], 'livekit')
        self.assertTrue(provider_payload['configured'])
        self.assertEqual(provider_payload['url'], 'wss://skillstudio-test.livekit.cloud')
        decoded = jwt.decode(
            provider_payload['token'],
            'test-livekit-secret',
            algorithms=['HS256'],
            issuer='test-livekit-key',
        )
        self.assertEqual(decoded['sub'], f'user-{self.student.id}')
        self.assertEqual(decoded['video']['room'], f'skillstudio-live-session-{self.session.id}')
        self.assertTrue(decoded['video']['roomJoin'])
        self.assertFalse(decoded['video']['canPublish'])
        self.assertTrue(decoded['video']['canSubscribe'])

    @override_settings(
        LIVEKIT_ENABLED=True,
        LIVEKIT_URL='wss://skillstudio-test.livekit.cloud',
        LIVEKIT_API_KEY='test-livekit-key',
        LIVEKIT_API_SECRET='test-livekit-secret',
    )
    def test_livekit_join_returns_publish_grant_for_instructor(self):
        self.session.platform = 'livekit'
        self.session.save(update_fields=['platform'])
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(f'/api/live/sessions/{self.session.id}/join/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        decoded = jwt.decode(
            response.data['provider']['token'],
            'test-livekit-secret',
            algorithms=['HS256'],
            issuer='test-livekit-key',
        )
        self.assertEqual(decoded['sub'], f'user-{self.instructor.id}')
        self.assertTrue(decoded['video']['canPublish'])
        self.assertTrue(decoded['video']['roomAdmin'])

    @override_settings(
        LIVEKIT_ENABLED=False,
        LIVEKIT_URL='',
        LIVEKIT_API_KEY='',
        LIVEKIT_API_SECRET='',
    )
    def test_livekit_join_reports_unconfigured_provider(self):
        self.session.platform = 'livekit'
        self.session.save(update_fields=['platform'])
        self.client.force_authenticate(user=self.student)

        response = self.client.post(f'/api/live/sessions/{self.session.id}/join/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['provider']['provider'], 'livekit')
        self.assertFalse(response.data['provider']['configured'])


class LiveWebSocketAccessControlTestCase(TransactionTestCase):
    """Regression tests for live WebSocket authentication and spoofing rules."""

    reset_sequences = True

    def setUp(self):
        self.instructor = User.objects.create_user(
            email='socket-owner@test.com',
            password='testpass123',
            role=User.Role.INSTRUCTOR
        )
        self.student = User.objects.create_user(
            email='socket-student@test.com',
            password='testpass123',
            role=User.Role.STUDENT
        )
        self.category = Category.objects.create(name='Socket Programming', slug='socket-programming')
        self.course = Course.objects.create(
            instructor=self.instructor,
            category=self.category,
            title='Socket Course',
            slug='socket-course',
            status='published'
        )
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active'
        )
        self.session = LiveSession.objects.create(
            course=self.course,
            instructor=self.instructor,
            title='Socket Session',
            scheduled_start=timezone.now() - timedelta(minutes=5),
            scheduled_end=timezone.now() + timedelta(hours=1),
            status='live',
            requires_enrollment=True,
            is_public=False,
        )

    def make_communicator(self, user=None):
        token_query = ''
        if user is not None:
            token_query = f'?token={AccessToken.for_user(user)}'
        communicator = WebsocketCommunicator(
            LiveStreamConsumer.as_asgi(),
            f'/ws/live/sessions/{self.session.id}/{token_query}'
        )
        communicator.scope['url_route'] = {'kwargs': {'session_id': str(self.session.id)}}
        return communicator

    def test_anonymous_socket_is_rejected(self):
        async_to_sync(self._anonymous_socket_is_rejected)()

    async def _anonymous_socket_is_rejected(self):
        communicator = self.make_communicator()
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    def test_student_socket_requires_joined_participant(self):
        async_to_sync(self._student_socket_requires_joined_participant)()

    async def _student_socket_requires_joined_participant(self):
        communicator = self.make_communicator(self.student)
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    def test_joined_student_cannot_send_instructor_offer(self):
        SessionParticipant.objects.create(
            session=self.session,
            user=self.student,
            status='joined',
            joined_at=timezone.now()
        )
        async_to_sync(self._joined_student_cannot_send_instructor_offer)()

    async def _joined_student_cannot_send_instructor_offer(self):
        communicator = self.make_communicator(self.student)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from(timeout=5)  # user_joined

        await communicator.send_json_to({
            'type': 'offer',
            'offer': {'type': 'offer', 'sdp': 'fake'},
            'sender_id': self.instructor.id,
        })
        response = await communicator.receive_json_from(timeout=5)

        self.assertEqual(response['type'], 'error')
        self.assertIn('Only the instructor', response['message'])
        await communicator.disconnect()

    def test_instructor_offer_uses_authenticated_sender_id(self):
        async_to_sync(self._instructor_offer_uses_authenticated_sender_id)()

    async def _instructor_offer_uses_authenticated_sender_id(self):
        communicator = self.make_communicator(self.instructor)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from(timeout=5)  # user_joined

        await communicator.send_json_to({
            'type': 'offer',
            'offer': {'type': 'offer', 'sdp': 'fake'},
            'sender_id': self.student.id,
        })
        response = await communicator.receive_json_from(timeout=5)

        self.assertEqual(response['type'], 'offer')
        self.assertEqual(response['sender_id'], self.instructor.id)
        await communicator.disconnect()
