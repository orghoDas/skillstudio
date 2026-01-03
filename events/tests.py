from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from .models import Event, EventRegistration, EventFeedback, EventAttendanceLog, EventResource
from courses.models import Course
from enrollments.models import Enrollment

User = get_user_model()


class EventModelTest(TestCase):
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
        
        self.event = Event.objects.create(
            title='Test Event',
            description='Test Description',
            event_type='workshop',
            course=self.course,
            scheduled_for=timezone.now() + timedelta(days=7),
            duration_minutes=120,
            max_seats=50,
            price=100.00,
            host=self.user
        )
    
    def test_event_creation(self):
        """Test event is created properly."""
        self.assertEqual(self.event.title, 'Test Event')
        self.assertEqual(self.event.event_type, 'workshop')
        self.assertEqual(self.event.status, 'draft')
    
    def test_available_seats(self):
        """Test available seats calculation."""
        self.assertEqual(self.event.available_seats(), 50)
        
        # Register some users
        EventRegistration.objects.create(
            event=self.event,
            user=self.user,
            status='confirmed'
        )
        
        self.assertEqual(self.event.available_seats(), 49)
    
    def test_is_full(self):
        """Test is_full method."""
        self.assertFalse(self.event.is_full())
        
        # Fill all seats
        for i in range(50):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@test.com',
                password='pass123'
            )
            EventRegistration.objects.create(
                event=self.event,
                user=user,
                status='confirmed'
            )
        
        self.assertTrue(self.event.is_full())


class EventRegistrationTest(APITestCase):
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
        
        # Enroll user in course
        Enrollment.objects.create(
            user=self.user,
            course=self.course
        )
        
        self.event = Event.objects.create(
            title='Test Event',
            description='Test Description',
            event_type='workshop',
            course=self.course,
            scheduled_for=timezone.now() + timedelta(days=7),
            max_seats=50,
            price=0.00,
            host=self.user,
            status='published'
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_register_for_event(self):
        """Test user can register for an event."""
        url = f'/api/events/{self.event.id}/register/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            EventRegistration.objects.filter(
                event=self.event,
                user=self.user
            ).exists()
        )
    
    def test_cannot_register_twice(self):
        """Test user cannot register for same event twice."""
        EventRegistration.objects.create(
            event=self.event,
            user=self.user,
            status='confirmed'
        )
        
        url = f'/api/events/{self.event.id}/register/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_cancel_registration(self):
        """Test user can cancel registration."""
        registration = EventRegistration.objects.create(
            event=self.event,
            user=self.user,
            status='confirmed'
        )
        
        url = f'/api/events/registration/{registration.id}/cancel/'
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        registration.refresh_from_db()
        self.assertEqual(registration.status, 'cancelled')


class EventFeedbackTest(APITestCase):
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
        
        self.event = Event.objects.create(
            title='Test Event',
            description='Test Description',
            event_type='workshop',
            course=self.course,
            scheduled_for=timezone.now() - timedelta(days=1),
            max_seats=50,
            price=0.00,
            host=self.user,
            status='completed'
        )
        
        self.registration = EventRegistration.objects.create(
            event=self.event,
            user=self.user,
            status='confirmed',
            attended=True
        )
        
        self.client.force_authenticate(user=self.user)
    
    def test_submit_feedback(self):
        """Test user can submit feedback."""
        url = f'/api/events/{self.event.id}/feedback/'
        data = {
            'rating': 5,
            'comment': 'Great event!'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            EventFeedback.objects.filter(
                event=self.event,
                user=self.user
            ).exists()
        )
    
    def test_cannot_submit_feedback_without_attendance(self):
        """Test user must attend to submit feedback."""
        self.registration.attended = False
        self.registration.save()
        
        url = f'/api/events/{self.event.id}/feedback/'
        data = {
            'rating': 5,
            'comment': 'Great event!'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EventAnalyticsTest(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            username='instructor',
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test Description',
            instructor=self.instructor
        )
        
        self.event = Event.objects.create(
            title='Test Event',
            description='Test Description',
            event_type='workshop',
            course=self.course,
            scheduled_for=timezone.now() - timedelta(days=1),
            max_seats=10,
            price=0.00,
            host=self.instructor,
            status='completed'
        )
        
        # Create registrations with attendance
        for i in range(5):
            user = User.objects.create_user(
                username=f'user{i}',
                email=f'user{i}@test.com',
                password='pass123'
            )
            registration = EventRegistration.objects.create(
                event=self.event,
                user=user,
                status='confirmed'
            )
            
            # Mark some as attended
            if i < 3:
                registration.attended = True
                registration.save()
                
                # Add feedback
                EventFeedback.objects.create(
                    event=self.event,
                    user=user,
                    rating=4 + (i % 2),
                    comment='Good event'
                )
        
        self.client.force_authenticate(user=self.instructor)
    
    def test_event_analytics(self):
        """Test event analytics endpoint."""
        url = f'/api/events/{self.event.id}/analytics/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_registrations'], 5)
        self.assertEqual(response.data['attended_count'], 3)
        self.assertEqual(response.data['attendance_rate'], '60.00')
        self.assertIn('average_rating', response.data)

