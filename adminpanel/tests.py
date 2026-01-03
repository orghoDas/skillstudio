from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta

from accounts.models import User
from courses.models import Course, Category
from payments.models import Payment, Payout
from adminpanel.models import AdminAction, ContentModerationQueue, PlatformSettings, SystemAlert
from adminpanel.services import (
    get_all_users, approve_instructor, suspend_user, activate_user,
    get_pending_courses, approve_course, reject_course,
    platform_stats, get_user_stats, get_revenue_stats,
)


class AdminPanelModelsTestCase(TestCase):
    """Test adminpanel models"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role='admin'
        )
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
    
    def test_admin_action_creation(self):
        """Test creating an admin action log"""
        action = AdminAction.objects.create(
            admin_user=self.admin_user,
            action_type='user_suspend',
            target_model='User',
            target_id=self.student.id,
            description='Test suspension'
        )
        
        self.assertEqual(action.admin_user, self.admin_user)
        self.assertEqual(action.action_type, 'user_suspend')
        self.assertEqual(action.target_id, self.student.id)
    
    def test_content_moderation_queue(self):
        """Test content moderation queue"""
        queue_item = ContentModerationQueue.objects.create(
            content_type='review',
            content_id=1,
            reported_by=self.student,
            reason='Inappropriate content',
            status='pending'
        )
        
        self.assertEqual(queue_item.status, 'pending')
        self.assertEqual(queue_item.reported_by, self.student)
    
    def test_platform_settings(self):
        """Test platform settings"""
        setting = PlatformSettings.objects.create(
            key='max_upload_size',
            value='10485760',
            description='Maximum upload size in bytes',
            data_type='integer'
        )
        
        self.assertEqual(setting.key, 'max_upload_size')
        self.assertEqual(setting.data_type, 'integer')
    
    def test_system_alert(self):
        """Test system alert"""
        alert = SystemAlert.objects.create(
            title='Maintenance Window',
            message='System will be down for maintenance',
            alert_type='maintenance',
            created_by=self.admin_user
        )
        
        self.assertTrue(alert.is_currently_active())
        self.assertEqual(alert.alert_type, 'maintenance')


class AdminPanelServicesTestCase(TestCase):
    """Test adminpanel services"""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role='admin'
        )
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
    
    def test_get_all_users(self):
        """Test getting all users"""
        users = get_all_users()
        self.assertEqual(users.count(), 3)
    
    def test_get_user_stats(self):
        """Test getting user statistics"""
        stats = get_user_stats()
        self.assertEqual(stats['total_users'], 3)
        self.assertEqual(stats['students'], 1)
        self.assertEqual(stats['instructors'], 1)
        self.assertEqual(stats['admins'], 1)
    
    def test_suspend_user(self):
        """Test suspending a user"""
        user = suspend_user(self.student.id, admin_user=self.admin_user, reason='Test suspension')
        self.assertFalse(user.is_active)
        
        # Check admin action was logged
        action = AdminAction.objects.filter(action_type='user_suspend').first()
        self.assertIsNotNone(action)
        self.assertEqual(action.admin_user, self.admin_user)
    
    def test_activate_user(self):
        """Test activating a suspended user"""
        self.student.is_active = False
        self.student.save()
        
        user = activate_user(self.student.id, admin_user=self.admin_user)
        self.assertTrue(user.is_active)
    
    def test_platform_stats(self):
        """Test getting platform statistics"""
        stats = platform_stats()
        self.assertIn('total_users', stats)
        self.assertIn('total_courses', stats)
        self.assertIn('total_enrollments', stats)


class AdminPanelAPITestCase(APITestCase):
    """Test adminpanel API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
        self.admin_user = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role='admin',
            is_staff=True
        )
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        
        self.client.force_authenticate(user=self.admin_user)
    
    def test_admin_dashboard_access(self):
        """Test admin dashboard access"""
        response = self.client.get('/api/adminpanel/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('platform_stats', response.data)
    
    def test_user_list_access(self):
        """Test user list access"""
        response = self.client.get('/api/adminpanel/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
    
    def test_suspend_user_endpoint(self):
        """Test suspending user via API"""
        response = self.client.post(
            f'/api/adminpanel/users/{self.student.id}/suspend/',
            {'reason': 'Test suspension'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify user is suspended
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
    
    def test_non_admin_access_denied(self):
        """Test non-admin users cannot access admin endpoints"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/adminpanel/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

