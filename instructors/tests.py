from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal
from unittest.mock import patch

from courses.models import Course
from enrollments.models import Enrollment
from payments.models import Payment
from .models import InstructorProfile, InstructorPayout
from .services import (
    get_or_create_instructor_profile,
    update_instructor_profile,
    request_payout,
    complete_payout,
)

User = get_user_model()


class InstructorProfileModelTests(TestCase):
    """Test InstructorProfile model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='instructor',
            email='instructor@example.com',
            password='testpass123'
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
    
    def test_update_statistics(self):
        """Test updating profile statistics."""
        profile = InstructorProfile.objects.create(user=self.user)
        
        # Create course
        course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        
        profile.update_statistics()
        
        self.assertEqual(profile.total_courses, 1)


class InstructorPayoutModelTests(TestCase):
    """Test InstructorPayout model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='instructor',
            email='instructor@example.com',
            password='testpass123'
        )
    
    def test_payout_creation(self):
        """Test creating a payout."""
        payout = InstructorPayout.objects.create(
            instructor=self.user,
            amount=Decimal('500.00')
        )
        
        self.assertEqual(payout.instructor, self.user)
        self.assertEqual(payout.amount, Decimal('500.00'))
        self.assertEqual(payout.status, 'pending')
    
    def test_complete_payout(self):
        """Test completing a payout."""
        payout = InstructorPayout.objects.create(
            instructor=self.user,
            amount=Decimal('500.00')
        )
        
        payout.complete('TXN12345')
        
        self.assertEqual(payout.status, 'completed')
        self.assertEqual(payout.transaction_id, 'TXN12345')
        self.assertIsNotNone(payout.processed_at)
    
    def test_fail_payout(self):
        """Test failing a payout."""
        payout = InstructorPayout.objects.create(
            instructor=self.user,
            amount=Decimal('500.00')
        )
        
        payout.fail('Insufficient funds')
        
        self.assertEqual(payout.status, 'failed')
        self.assertIn('Insufficient funds', payout.notes)


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
        profile = get_or_create_instructor_profile(self.user)
        
        updated = update_instructor_profile(
            self.user,
            bio='New bio',
            headline='Expert Instructor',
            years_of_experience=15
        )
        
        self.assertEqual(updated.bio, 'New bio')
        self.assertEqual(updated.headline, 'Expert Instructor')
        self.assertEqual(updated.years_of_experience, 15)
    
    def test_update_nonexistent_profile(self):
        """Test updating profile that doesn't exist."""
        with self.assertRaises(ValidationError):
            update_instructor_profile(self.user, bio='Test')


class InstructorPayoutServiceTests(TestCase):
    """Test instructor payout services."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='instructor',
            email='instructor@example.com',
            password='testpass123'
        )
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123',
            is_staff=True
        )
        
        # Create some earnings
        Payment.objects.create(
            user=self.user,  # Required field
            instructor=self.user,
            amount=Decimal('1000.00'),
            original_amount=Decimal('1000.00'),
            instructor_earnings=Decimal('700.00'),
            platform_fee=Decimal('300.00'),
            status='completed'
        )
    
    def test_request_payout_success(self):
        """Test requesting a payout."""
        payout = request_payout(
            self.user,
            Decimal('500.00'),
            payment_method='bank_transfer'
        )
        
        self.assertIsNotNone(payout)
        self.assertEqual(payout.amount, Decimal('500.00'))
        self.assertEqual(payout.status, 'pending')
    
    def test_request_payout_invalid_amount(self):
        """Test requesting payout with invalid amount."""
        with self.assertRaises(ValidationError):
            request_payout(self.user, Decimal('0.00'))
    
    def test_request_payout_insufficient_balance(self):
        """Test requesting payout with insufficient balance."""
        with self.assertRaises(ValidationError):
            request_payout(self.user, Decimal('1000.00'))
    
    def test_complete_payout_as_admin(self):
        """Test completing payout as admin."""
        payout = request_payout(self.user, Decimal('500.00'))
        
        completed = complete_payout(payout.id, 'TXN123', self.admin)
        
        self.assertEqual(completed.status, 'completed')
        self.assertEqual(completed.transaction_id, 'TXN123')
    
    def test_complete_payout_as_non_admin(self):
        """Test completing payout as non-admin."""
        payout = request_payout(self.user, Decimal('500.00'))
        
        with self.assertRaises(PermissionDenied):
            complete_payout(payout.id, 'TXN123', self.user)
