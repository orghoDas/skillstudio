from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from datetime import timedelta

from courses.models import Course, Category
from .models import QuestionBank, Exam, ExamAttempt, ExamResult
from .services import start_exam_attempt, submit_exam_attempt
# get_exam_analytics kept local to exams app

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
        self.assertEqual(attempt.attempt_number, 1)

    def test_start_exam_attempt_reuses_active_attempt(self):
        first = start_exam_attempt(self.exam, self.student)
        second = start_exam_attempt(self.exam, self.student)

        self.assertEqual(second.id, first.id)
        self.assertEqual(second.attempt_number, 1)
        self.assertEqual(
            ExamAttempt.objects.filter(exam=self.exam, user=self.student).count(),
            1
        )

    def test_start_exam_attempt_numbers_next_allowed_attempt(self):
        first = start_exam_attempt(self.exam, self.student)
        first.status = 'completed'
        first.completed_at = timezone.now()
        first.save(update_fields=['status', 'completed_at'])

        second = start_exam_attempt(self.exam, self.student)

        self.assertNotEqual(second.id, first.id)
        self.assertEqual(second.attempt_number, 2)
        self.assertEqual(second.status, 'in_progress')
    
    def test_max_attempts_limit(self):
        """Test max attempts enforcement."""
        # Create 2 completed attempts
        for attempt_number in range(1, 3):
            ExamAttempt.objects.create(
                exam=self.exam,
                user=self.student,
                attempt_number=attempt_number,
                status='completed'
            )
        
        # Try to start 3rd attempt
        with self.assertRaises(ValueError):
            start_exam_attempt(self.exam, self.student)

    def test_expired_active_attempt_is_abandoned_and_counts_toward_limit(self):
        first = start_exam_attempt(self.exam, self.student)
        first.started_at = timezone.now() - timedelta(hours=2)
        first.save(update_fields=['started_at'])

        second = start_exam_attempt(self.exam, self.student)

        first.refresh_from_db()
        self.assertEqual(first.status, 'abandoned')
        self.assertEqual(second.attempt_number, 2)

        second.status = 'completed'
        second.completed_at = timezone.now()
        second.save(update_fields=['status', 'completed_at'])

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

    def test_exam_scoring_uses_actual_question_marks_and_accepts_text_answer(self):
        attempt = start_exam_attempt(self.exam, self.student)

        submitted = submit_exam_attempt(attempt, {str(self.q1.id): "Correct"})

        self.assertEqual(submitted.score, Decimal('10'))
        self.assertEqual(submitted.percentage, Decimal('100'))

    def test_exam_scoring_includes_custom_questions(self):
        self.exam.custom_questions = [
            {
                'id': 'custom-1',
                'question_text': 'Custom MCQ',
                'marks': 5,
                'options': [
                    {'text': 'Wrong', 'is_correct': False},
                    {'text': 'Right', 'is_correct': True},
                ],
            }
        ]
        self.exam.save(update_fields=['custom_questions'])
        attempt = start_exam_attempt(self.exam, self.student)

        submitted = submit_exam_attempt(
            attempt,
            {
                str(self.q1.id): 0,
                'custom-1': 'Right',
            }
        )

        self.assertEqual(submitted.score, Decimal('15'))
        self.assertEqual(submitted.percentage, Decimal('100'))

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

    def test_start_exam_reuses_active_attempt_and_returns_attempt_number(self):
        url = f'/api/exams/{self.exam.id}/start/'

        first = self.client.post(url)
        second = self.client.post(url)

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_201_CREATED)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(first.data['attempt_number'], 1)
        self.assertEqual(second.data['attempt_number'], 1)
        self.assertEqual(
            ExamAttempt.objects.filter(exam=self.exam, user=self.student).count(),
            1
        )


class ExamAccessControlAPITest(APITestCase):
    """Regression tests for exam access and answer disclosure."""

    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        self.other_student = User.objects.create_user(
            email='other-student@test.com',
            password='testpass123',
            role='student'
        )
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.other_instructor = User.objects.create_user(
            email='other-instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name='Tech', slug='tech-access')
        self.course = Course.objects.create(
            title='Secure Exam Course',
            instructor=self.instructor,
            category=self.category,
            status='published'
        )
        self.other_course = Course.objects.create(
            title='Other Instructor Course',
            instructor=self.other_instructor,
            category=self.category,
            status='published'
        )
        self.exam = Exam.objects.create(
            course=self.course,
            title='Secure Final Exam',
            total_marks=100,
            duration_minutes=60,
            status='published',
            custom_questions=[
                {
                    'question_text': 'Custom question',
                    'options': [
                        {'text': 'A', 'is_correct': False},
                        {'text': 'B', 'is_correct': True},
                    ],
                    'explanation': 'Private explanation',
                }
            ],
            created_by=self.instructor
        )
        self.question = QuestionBank.objects.create(
            course=self.course,
            question_text='What is 2 + 2?',
            question_type='mcq',
            difficulty='easy',
            options=[
                {'text': '3', 'is_correct': False},
                {'text': '4', 'is_correct': True},
            ],
            explanation='Private explanation',
            marks=5,
            created_by=self.instructor
        )
        self.exam.questions.add(self.question)

        from enrollments.models import Enrollment
        Enrollment.objects.create(user=self.student, course=self.course, status='active')

        self.other_exam = Exam.objects.create(
            course=self.other_course,
            title='Other Instructor Exam',
            total_marks=100,
            duration_minutes=60,
            status='published',
            created_by=self.other_instructor
        )
        self.other_attempt = ExamAttempt.objects.create(
            exam=self.exam,
            user=self.other_student
        )

    def test_student_exam_detail_hides_correct_answer_data(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get(f'/api/exams/{self.exam.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        question_data = response.data['questions'][0]
        self.assertNotIn('correct_answer', question_data)
        self.assertNotIn('explanation', question_data)
        self.assertNotIn('is_correct', question_data['options'][0])
        self.assertNotIn('is_correct', question_data['options'][1])

        custom_question = response.data['custom_questions'][0]
        self.assertNotIn('correct_answer', custom_question)
        self.assertNotIn('explanation', custom_question)
        self.assertNotIn('is_correct', custom_question['options'][0])
        self.assertNotIn('is_correct', custom_question['options'][1])

    def test_non_enrolled_student_cannot_start_exam(self):
        self.client.force_authenticate(user=self.other_student)

        response = self.client.post(f'/api/exams/{self.exam.id}/start/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_submit_another_students_attempt(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.post(
            f'/api/exams/{self.exam.id}/submit/',
            {
                'attempt_id': self.other_attempt.id,
                'answers': {str(self.question.id): 1},
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instructor_cannot_view_other_instructors_exam_attempts(self):
        self.client.force_authenticate(user=self.instructor)

        response = self.client.get(f'/api/exams/{self.other_exam.id}/all-attempts/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


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

    def test_create_question_rejects_short_answer_type(self):
        url = '/api/exams/questions/'
        data = {
            'course': self.course.id,
            'question_text': 'Explain polymorphism.',
            'question_type': 'short',
            'difficulty': 'medium',
            'options': [],
            'marks': 5,
        }

        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(QuestionBank.objects.count(), 0)
