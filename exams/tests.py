from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from datetime import timedelta

from courses.models import Course, Category
from .models import QuestionBank, Exam, ExamAttempt, ExamResult
from .services import start_exam_attempt, submit_exam_attempt, get_exam_analytics

User = get_user_model()


# ===========================
# 🧪 Model Tests
# ===========================

class QuestionBankModelTest(TestCase):
    """Test QuestionBank model functionality."""
    
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name='Technology', slug='technology')
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.instructor,
            category=self.category
        )
    
    def test_question_creation(self):
        """Test creating a question."""
        question = QuestionBank.objects.create(
            course=self.course,
            question_text='What is Python?',
            question_type='mcq',
            difficulty='easy',
            options=[
                {"text": "Programming Language", "is_correct": True},
                {"text": "Snake", "is_correct": False}
            ],
            marks=5,
            created_by=self.instructor
        )
        
        self.assertEqual(question.question_text, 'What is Python?')
        self.assertEqual(question.difficulty, 'easy')
        self.assertEqual(len(question.options), 2)


class ExamModelTest(TestCase):
    """Test Exam model functionality."""
    
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(
            title='Course',
            instructor=self.instructor,
            category=self.category
        )
    
    def test_exam_creation(self):
        """Test creating an exam."""
        exam = Exam.objects.create(
            course=self.course,
            title='Final Exam',
            total_marks=100,
            passing_marks=60,
            duration_minutes=120,
            created_by=self.instructor
        )
        
        self.assertEqual(exam.title, 'Final Exam')
        self.assertEqual(exam.total_marks, 100)
        self.assertEqual(exam.status, 'draft')
    
    def test_exam_is_active(self):
        """Test exam active status."""
        exam = Exam.objects.create(
            course=self.course,
            title='Active Exam',
            duration_minutes=60,
            status='published',
            created_by=self.instructor
        )
        
        self.assertTrue(exam.is_active())
        
        # Set past end date
        exam.end_datetime = timezone.now() - timedelta(days=1)
        exam.save()
        
        self.assertFalse(exam.is_active())


class ExamAttemptModelTest(TestCase):
    """Test ExamAttempt model functionality."""
    
    def setUp(self):
        self.student = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category)
        
        self.exam = Exam.objects.create(
            course=self.course,
            title='Test Exam',
            total_marks=100,
            duration_minutes=60,
            status='published',
            created_by=self.instructor
        )
    
    def test_exam_attempt_creation(self):
        """Test creating exam attempt."""
        attempt = ExamAttempt.objects.create(
            exam=self.exam,
            user=self.student
        )
        
        self.assertEqual(attempt.exam, self.exam)
        self.assertEqual(attempt.user, self.student)
        self.assertEqual(attempt.status, 'in_progress')
    
    def test_time_remaining(self):
        """Test time remaining calculation."""
        attempt = ExamAttempt.objects.create(exam=self.exam, user=self.student)
        
        remaining = attempt.time_remaining_seconds()
        self.assertIsNotNone(remaining)
        self.assertGreater(remaining, 0)
    
    def test_is_expired(self):
        """Test expiry check."""
        attempt = ExamAttempt.objects.create(
            exam=self.exam,
            user=self.student
        )
        # Update started_at to past time (auto_now_add ignores passed values)
        past_time = timezone.now() - timedelta(hours=2)
        attempt.started_at = past_time
        attempt.save()
        
        self.assertTrue(attempt.is_expired())


# ===========================
# 🔧 Service Tests
# ===========================

class ExamServicesTest(TestCase):
    """Test exam service functions."""
    
    def setUp(self):
        self.student = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category)
        
        self.exam = Exam.objects.create(
            course=self.course,
            title='Test Exam',
            total_marks=100,
            duration_minutes=60,
            status='published',
            max_attempts=2,
            created_by=self.instructor
        )
        
        # Create questions
        self.q1 = QuestionBank.objects.create(
            course=self.course,
            question_text='Q1',
            question_type='mcq',
            options=[
                {"text": "Correct", "is_correct": True},
                {"text": "Wrong", "is_correct": False}
            ],
            marks=10,
            created_by=self.instructor
        )
        
        self.exam.questions.add(self.q1)
    
    def test_start_exam_attempt(self):
        """Test starting exam attempt."""
        attempt = start_exam_attempt(self.exam, self.student)
        
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.exam, self.exam)
        self.assertEqual(attempt.user, self.student)
        self.assertEqual(attempt.status, 'in_progress')
    
    def test_max_attempts_limit(self):
        """Test max attempts enforcement."""
        # Create 2 completed attempts
        for _ in range(2):
            attempt = ExamAttempt.objects.create(
                exam=self.exam,
                user=self.student,
                status='completed'
            )
        
        # Try to start 3rd attempt
        with self.assertRaises(ValueError):
            start_exam_attempt(self.exam, self.student)
    
    def test_submit_exam_attempt(self):
        """Test submitting exam attempt."""
        attempt = start_exam_attempt(self.exam, self.student)
        
        answers = {
            str(self.q1.id): "Correct"
        }
        
        submitted = submit_exam_attempt(attempt, answers)
        
        self.assertEqual(submitted.status, 'completed')
        self.assertIsNotNone(submitted.score)
        self.assertIsNotNone(submitted.completed_at)


# ===========================
# 🌐 API Tests
# ===========================

class ExamAPITest(APITestCase):
    """Test exam API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.student = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(
            title='Course',
            instructor=self.instructor,
            category=self.category,
            status='published'
        )
        
        self.exam = Exam.objects.create(
            course=self.course,
            title='Test Exam',
            total_marks=100,
            duration_minutes=60,
            status='published',
            created_by=self.instructor
        )
        
        # Enroll student
        from enrollments.models import Enrollment
        Enrollment.objects.create(user=self.student, course=self.course, status='active')
        
        self.client.force_authenticate(user=self.student)
    
    def test_get_course_exams(self):
        """Test getting exams for a course."""
        url = f'/api/exams/course/{self.course.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class QuestionBankAPITest(APITestCase):
    """Test question bank API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(
            title='Course',
            instructor=self.instructor,
            category=self.category
        )
        
        self.client.force_authenticate(user=self.instructor)
    
    def test_create_question(self):
        """Test creating a question via API."""
        url = '/api/exams/questions/'
        data = {
            'course': self.course.id,
            'question_text': 'What is 2+2?',
            'question_type': 'mcq',
            'difficulty': 'easy',
            'options': [
                {"text": "3", "is_correct": False},
                {"text": "4", "is_correct": True}
            ],
            'marks': 5
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(QuestionBank.objects.count(), 1)

