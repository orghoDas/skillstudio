from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from unittest.mock import patch
from rest_framework.test import APIClient

from courses.models import Course
from enrollments.models import Enrollment
from payments.models import Payment, Refund
from .models import InstructorProfile
from .services import (
    get_or_create_instructor_profile,
    update_instructor_profile,
)

User = get_user_model()


class InstructorDashboardErrorTests(TestCase):
    def test_unexpected_failure_returns_500_instead_of_empty_dashboard(self):
        instructor = User.objects.create_user(email='dashboard-error@example.test', role='instructor')
        client = APIClient()
        client.force_authenticate(instructor)

        with (
            patch('instructors.views.get_course_overview', side_effect=TypeError('Internal analytics failure')),
            self.assertLogs('core.api_exceptions', level='ERROR') as logs,
        ):
            response = client.get('/api/instructors/dashboard/')

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()['code'], 'internal_error')
        self.assertNotIn('Internal analytics failure', response.content.decode())
        self.assertIn('TypeError: Internal analytics failure', logs.output[0])


class InstructorProfileModelTests(TestCase):
    """Test InstructorProfile model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='instructor',
            email='instructor@example.com',
            password='testpass123',
            role='instructor',
        )
    
    def test_profile_creation(self):
        """Test creating an instructor profile."""
        profile = InstructorProfile.objects.create(
            user=self.user,
            bio='Experienced instructor',
            headline='Senior Developer',
            years_of_experience=10
        )
        
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.bio, 'Experienced instructor')
        self.assertFalse(profile.is_verified)
    
    def test_verify_instructor(self):
        """Test verifying an instructor."""
        profile = InstructorProfile.objects.create(user=self.user)
        
        self.assertFalse(profile.is_verified)
        self.assertIsNone(profile.verified_at)
        
        profile.verify()
        
        self.assertTrue(profile.is_verified)
        self.assertIsNotNone(profile.verified_at)
    
    def test_statistics_follow_new_courses_students_and_refunds(self):
        profile = InstructorProfile.objects.create(user=self.user)
        self.assertEqual(profile.total_courses, 0)
        
        # Create course
        course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        
        second = Course.objects.create(title='Second course', instructor=self.user)
        student = User.objects.create_user(email='one-student@example.test')
        for enrolled_course in (course, second):
            Enrollment.objects.create(user=student, course=enrolled_course)
        payment = Payment.objects.create(
            user=student, instructor=self.user, course=course, status='partially_refunded',
            amount=100, original_amount=100, instructor_earnings=90,
        )
        Refund.objects.create(payment=payment, status='processed', amount=50, instructor_debit=45)
        self.assertEqual((profile.total_courses, profile.total_students, profile.total_revenue), (2, 1, Decimal('45.00')))

        client = APIClient()
        client.force_authenticate(self.user)
        response = client.get('/api/instructors/profile/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['total_revenue'], '45.00')
        self.assertEqual(response.data['total_students'], 1)
        account = client.get('/api/accounts/profile/').data['instructor_profile']
        self.assertEqual(account['total_courses'], 2)
        self.assertEqual(account['total_revenue'], '45.00')


class InstructorProfileServiceTests(TestCase):
    """Test instructor profile services."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='instructor',
            email='instructor@example.com',
            password='testpass123'
        )
    
    def test_get_or_create_profile(self):
        """Test getting or creating profile."""
        profile = get_or_create_instructor_profile(self.user)
        
        self.assertIsNotNone(profile)
        self.assertEqual(profile.user, self.user)
        
        # Should return same profile on second call
        profile2 = get_or_create_instructor_profile(self.user)
        self.assertEqual(profile.id, profile2.id)
    
    def test_update_profile(self):
        """Test updating profile."""
        get_or_create_instructor_profile(self.user)
        
        updated = update_instructor_profile(
            self.user,
            bio='New bio',
            headline='Expert Instructor',
            years_of_experience=15
        )
        
        self.assertEqual(updated.bio, 'New bio')
        self.assertEqual(updated.headline, 'Expert Instructor')
        self.assertEqual(updated.years_of_experience, 15)
    
    def test_update_creates_missing_profile(self):
        updated = update_instructor_profile(self.user, bio='Test')
        self.assertEqual(updated.bio, 'Test')


# Payout tests moved to payments/tests.py (wallet-ledger payouts, PAY-07).
