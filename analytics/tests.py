from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import timedelta
from decimal import Decimal

from accounts.models import User
from courses.models import Course, Category, Module, Lesson
from enrollments.models import Enrollment, LessonProgress
from payments.models import Payment
from analytics.models import (
    CourseAnalyticsSnapshot,
    UserInteraction,
    InstructorAnalytics,
    LessonAnalytics,
    DailyPlatformMetrics,
)
from analytics.services import (
    get_course_analytics,
    get_instructor_analytics,
    get_student_analytics,
    track_user_interaction,
)


class AnalyticsModelsTestCase(TestCase):
    """Test analytics models"""
    
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
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.course = Course.objects.create(
            title='Test Course',
            slug='test-course',
            instructor=self.instructor,
            category=self.category,
            status='published'
        )
    
    def test_course_analytics_snapshot_creation(self):
        """Test creating a course analytics snapshot"""
        snapshot = CourseAnalyticsSnapshot.objects.create(
            course=self.course,
            snapshot_date=timezone.now().date(),
            total_enrollments=10,
            total_completions=5,
            total_revenue=Decimal('1000.00')
        )
        
        self.assertEqual(snapshot.course, self.course)
        self.assertEqual(snapshot.total_enrollments, 10)
    
    def test_user_interaction_tracking(self):
        """Test tracking user interactions"""
        interaction = UserInteraction.objects.create(
            user=self.user,
            course=self.course,
            action='view_course',
            metadata={'source': 'homepage'}
        )
        
        self.assertEqual(interaction.user, self.user)
        self.assertEqual(interaction.action, 'view_course')
    
    def test_instructor_analytics(self):
        """Test instructor analytics model"""
        analytics = InstructorAnalytics.objects.create(
            instructor=self.instructor,
            total_courses=5,
            total_students=50,
            total_revenue=Decimal('5000.00')
        )
        
        self.assertEqual(analytics.instructor, self.instructor)
        self.assertEqual(analytics.total_courses, 5)
    
    def test_daily_platform_metrics(self):
        """Test daily platform metrics"""
        metrics = DailyPlatformMetrics.objects.create(
            date=timezone.now().date(),
            total_users=100,
            new_users=10,
            total_enrollments=500
        )
        
        self.assertEqual(metrics.total_users, 100)
        self.assertEqual(metrics.new_users, 10)


class AnalyticsServicesTestCase(TestCase):
    """Test analytics services"""
    
    def setUp(self):
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
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.course = Course.objects.create(
            title='Test Course',
            slug='test-course',
            instructor=self.instructor,
            category=self.category,
            status='published'
        )
        
        # Create module and lessons
        self.module = Module.objects.create(
            course=self.course,
            title='Test Module',
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Test Lesson',
            content_type='text',
            content_text='Test content',
            position=1
        )
        
        # Create enrollment
        self.enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course
        )
    
    def test_get_course_analytics(self):
        """Test getting course analytics"""
        analytics = get_course_analytics(self.course.id, instructor=self.instructor)
        
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics['course_id'], self.course.id)
        self.assertEqual(analytics['total_enrollments'], 1)
    
    def test_get_instructor_analytics(self):
        """Test getting instructor analytics"""
        analytics = get_instructor_analytics(self.instructor)
        
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics['instructor_id'], self.instructor.id)
        self.assertEqual(analytics['total_courses'], 1)
    
    def test_get_student_analytics(self):
        """Test getting student analytics"""
        analytics = get_student_analytics(self.student)
        
        self.assertIsNotNone(analytics)
        self.assertEqual(analytics['student_id'], self.student.id)
        self.assertEqual(analytics['total_enrollments'], 1)
    
    def test_track_user_interaction(self):
        """Test tracking user interaction"""
        interaction = track_user_interaction(
            user=self.student,
            action='view_course',
            course=self.course,
            metadata={'source': 'search'}
        )
        
        self.assertIsNotNone(interaction)
        self.assertEqual(interaction.user, self.student)
        self.assertEqual(interaction.action, 'view_course')


class AnalyticsAPITestCase(APITestCase):
    """Test analytics API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        
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
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.course = Course.objects.create(
            title='Test Course',
            slug='test-course',
            instructor=self.instructor,
            category=self.category,
            status='published'
        )
        
        self.enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course
        )
    
    def test_instructor_course_analytics_access(self):
        """Test instructor accessing course analytics"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(f'/api/analytics/instructor/course/{self.course.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('course_id', response.data)
    
    def test_instructor_dashboard_analytics(self):
        """Test instructor dashboard analytics"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get('/api/analytics/instructor/dashboard/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overview', response.data)
    
    def test_student_analytics_access(self):
        """Test student accessing their analytics"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/analytics/student/dashboard/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('student_id', response.data)
    
    def test_student_progress_report(self):
        """Test student progress report"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/analytics/student/course/{self.course.id}/progress/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('course_id', response.data)
    
    def test_track_interaction_endpoint(self):
        """Test tracking interaction via API"""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            '/api/analytics/track/',
            {
                'action': 'view_course',
                'course_id': self.course.id,
                'metadata': {'source': 'homepage'}
            },
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('interaction_id', response.data)
    
    def test_unauthorized_access_instructor_analytics(self):
        """Test unauthorized access to instructor analytics"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/analytics/instructor/course/{self.course.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

