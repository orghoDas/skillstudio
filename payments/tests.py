"""
Payment Tests
Comprehensive tests for payment models, services, and APIs
"""

from django.test import TestCase
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from courses.models import Course, Category
from events.models import Event
from payments.models import (
    Payment, Payout, Refund, Coupon, CouponRedemption
)
from payments import services


# ==========================================
# MODEL TESTS
# ==========================================

class PaymentModelsTestCase(TestCase):
    """Test payment models"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name='Test Category', slug='test')
        self.course = Course.objects.create(
            title='Test Course',
            slug='test-course',
            instructor=self.instructor,
            category=self.category,
            status='published',
            price=Decimal('99.99')
        )
    
    def test_payment_creation(self):
        """Test creating a payment"""
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=Decimal('99.99'),
            original_amount=Decimal('99.99'),
            currency='USD',
            payment_method='stripe'
        )
        
        self.assertEqual(payment.user, self.user)
        self.assertEqual(payment.course, self.course)
        self.assertEqual(payment.amount, Decimal('99.99'))
        self.assertEqual(payment.status, 'pending')
    
    def test_payout_creation(self):
        """Test creating a payout"""
        payout = Payout.objects.create(
            instructor=self.instructor,
            amount=Decimal('50.00'),
            currency='USD',
            payout_method='stripe_connect'
        )
        
        self.assertEqual(payout.instructor, self.instructor)
        self.assertEqual(payout.amount, Decimal('50.00'))
        self.assertEqual(payout.status, 'pending')
    
    def test_coupon_creation(self):
        """Test creating a coupon"""
        coupon = Coupon.objects.create(
            code='TEST20',
            discount_type='percent',
            discount_value=Decimal('20.00'),
            created_by=self.instructor
        )
        
        self.assertEqual(coupon.code, 'TEST20')
        self.assertTrue(coupon.is_valid)
    
    def test_refund_creation(self):
        """Test creating a refund"""
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=Decimal('99.99'),
            original_amount=Decimal('99.99'),
            status='completed'
        )
        
        refund = Refund.objects.create(
            payment=payment,
            requested_by=self.user,
            amount=Decimal('99.99'),
            reason='Not satisfied',
            refund_type='full'
        )
        
        self.assertEqual(refund.payment, payment)
        self.assertEqual(refund.status, 'requested')


# ==========================================
# SERVICE TESTS
# ==========================================

class PaymentServicesTestCase(TestCase):
    """Test payment services"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name='Test Category', slug='test')
        self.course = Course.objects.create(
            title='Test Course',
            slug='test-course',
            instructor=self.instructor,
            category=self.category,
            status='published',
            price=Decimal('100.00')
        )
    
    def test_create_payment(self):
        """Test creating a payment"""
        payment = services.create_payment(
            user=self.user,
            amount=Decimal('100.00'),
            course=self.course,
            payment_method='stripe'
        )
        
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, Decimal('100.00'))
        self.assertEqual(payment.status, 'pending')
    
    def test_process_payment_success(self):
        """Test processing successful payment"""
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=Decimal('100.00'),
            original_amount=Decimal('100.00'),
            status='pending'
        )
        
        payment = services.process_payment_success(
            payment=payment,
            provider_id='pi_test123'
        )
        
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(payment.instructor, self.instructor)
        self.assertEqual(payment.platform_fee, Decimal('20.00'))
        self.assertEqual(payment.instructor_earnings, Decimal('80.00'))
    
    def test_coupon_discount_calculation(self):
        """Test coupon discount calculation"""
        # Percentage coupon
        coupon = Coupon.objects.create(
            code='SAVE20',
            discount_type='percent',
            discount_value=Decimal('20.00'),
            created_by=self.instructor
        )
        
        discount = services.calculate_coupon_discount(coupon, Decimal('100.00'))
        self.assertEqual(discount, Decimal('20.00'))
        
        # Fixed coupon
        fixed_coupon = Coupon.objects.create(
            code='SAVE10',
            discount_type='fixed',
            discount_value=Decimal('10.00'),
            created_by=self.instructor
        )
        
        discount = services.calculate_coupon_discount(fixed_coupon, Decimal('100.00'))
        self.assertEqual(discount, Decimal('10.00'))
    
    def test_calculate_instructor_balance(self):
        """Test calculating instructor balance"""
        # Create completed payment
        Payment.objects.create(
            user=self.user,
            course=self.course,
            instructor=self.instructor,
            amount=Decimal('100.00'),
            original_amount=Decimal('100.00'),
            instructor_earnings=Decimal('80.00'),
            status='completed'
        )
        
        balance = services.calculate_instructor_balance(self.instructor)
        
        self.assertEqual(balance['total_earnings'], Decimal('80.00'))
        self.assertEqual(balance['available'], Decimal('80.00'))
    
    def test_request_refund(self):
        """Test requesting a refund"""
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=Decimal('100.00'),
            original_amount=Decimal('100.00'),
            status='completed'
        )
        
        refund = services.request_refund(
            payment=payment,
            amount=Decimal('100.00'),
            reason='Test refund',
            user=self.user,
            refund_type='full'
        )
        
        self.assertIsNotNone(refund)
        self.assertEqual(refund.status, 'requested')
        self.assertEqual(refund.amount, Decimal('100.00'))


# ==========================================
# API TESTS
# ==========================================

class PaymentAPITestCase(APITestCase):
    """Test payment API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role='admin',
            is_staff=True
        )
        
        self.category = Category.objects.create(name='Test Category', slug='test')
        self.course = Course.objects.create(
            title='Test Course',
            slug='test-course',
            instructor=self.instructor,
            category=self.category,
            status='published',
            price=Decimal('100.00')
        )
    
    def test_payment_list(self):
        """Test listing user payments"""
        Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal('100.00'),
            original_amount=Decimal('100.00')
        )
        
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/payments/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
    
    def test_create_payment(self):
        """Test creating a payment via API"""
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/payments/create/', {
            'course_id': self.course.id,
            'amount': '100.00',
            'payment_method': 'stripe'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
    
    def test_coupon_validation(self):
        """Test validating a coupon"""
        coupon = Coupon.objects.create(
            code='TEST20',
            discount_type='percent',
            discount_value=Decimal('20.00'),
            created_by=self.instructor
        )
        
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/payments/coupons/validate/', {
            'code': 'TEST20',
            'amount': '100.00',
            'course_id': self.course.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['valid'])
        self.assertEqual(float(response.data['discount_amount']), 20.00)
    
    def test_payout_balance(self):
        """Test getting instructor balance"""
        Payment.objects.create(
            user=self.student,
            course=self.course,
            instructor=self.instructor,
            amount=Decimal('100.00'),
            original_amount=Decimal('100.00'),
            instructor_earnings=Decimal('80.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get('/api/payments/payouts/balance/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['available']), 80.00)
    
    def test_refund_request(self):
        """Test requesting a refund"""
        payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal('100.00'),
            original_amount=Decimal('100.00'),
            status='completed'
        )
        
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/payments/refunds/request/', {
            'payment_id': payment.id,
            'amount': '100.00',
            'reason': 'Not satisfied',
            'refund_type': 'full'
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
    
    def test_coupon_create_admin_only(self):
        """Test that only admins can create coupons"""
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/payments/coupons/create/', {
            'code': 'STUDENT20',
            'discount_type': 'percent',
            'discount_value': '20.00'
        })
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin can create
        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/payments/coupons/create/', {
            'code': 'ADMIN20',
            'discount_type': 'percent',
            'discount_value': '20.00',
            'applies_to': 'all'  # Required field
        })
        
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Error: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
