from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from datetime import timedelta

from courses.models import Course, Module, Lesson, Category
from .models import Quiz, QuizQuestion, QuestionOption, QuizAttempt, Assignment, Submission, Rubric
from .services import start_quiz_attempt, submit_quiz_attempt, submit_assignment
from .services_scoring import calculate_quiz_score
from .grading_services import grade_submission, grade_submission_with_rubric

User = get_user_model()


# ===========================
# 🧪 Model Tests
# ===========================

class QuizModelTest(TestCase):
    """Test Quiz model functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='student@test.com',
            password='testpass123'
        )
        
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        
        self.category = Category.objects.create(name='Technology', slug='technology')
        
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.instructor,
            category=self.category,
            status='published'
        )
        
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1',
            position=1
        )
        
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            content_type='text',
            content_text='Lesson content',
            position=1
        )
    
    def test_quiz_creation(self):
        """Test creating a quiz."""
        quiz = Quiz.objects.create(
            lesson=self.lesson,
            title='Test Quiz',
            total_marks=100,
            time_limit_minutes=30
        )
        
        self.assertEqual(quiz.lesson, self.lesson)
        self.assertEqual(quiz.title, 'Test Quiz')
        self.assertTrue(quiz.has_time_limit())
    
    def test_quiz_without_time_limit(self):
        """Test quiz without time limit."""
        quiz = Quiz.objects.create(
            lesson=self.lesson,
            title='Untimed Quiz',
            total_marks=50
        )
        
        self.assertFalse(quiz.has_time_limit())


class QuizQuestionModelTest(TestCase):
    """Test QuizQuestion model functionality."""
    
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
        
        self.module = Module.objects.create(course=self.course, title='Module 1', position=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson 1', content_type='text', content_text='Lesson content', position=1)
        self.quiz = Quiz.objects.create(lesson=self.lesson, title='Test Quiz')
    
    def test_mcq_question_creation(self):
        """Test creating MCQ question."""
        question = QuizQuestion.objects.create(
            quiz=self.quiz,
            question_text='What is 2+2?',
            question_type='mcq',
            difficulty='easy',
            marks=5
        )
        
        self.assertEqual(question.question_type, 'mcq')
        self.assertEqual(question.marks, 5)
    
    def test_true_false_question_creation(self):
        """Test creating True/False question."""
        question = QuizQuestion.objects.create(
            quiz=self.quiz,
            question_text='Python is a programming language',
            question_type='tf',
            difficulty='easy',
            marks=2
        )
        
        self.assertEqual(question.question_type, 'tf')


class QuizAttemptModelTest(TestCase):
    """Test QuizAttempt model functionality."""
    
    def setUp(self):
        self.user = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category)
        self.module = Module.objects.create(course=self.course, title='Module', position=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson', content_type='text', content_text='Lesson content', position=1)
        self.quiz = Quiz.objects.create(lesson=self.lesson, title='Quiz', time_limit_minutes=30)
    
    def test_quiz_attempt_creation(self):
        """Test creating quiz attempt."""
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            user=self.user
        )
        
        self.assertEqual(attempt.quiz, self.quiz)
        self.assertEqual(attempt.user, self.user)
        self.assertIsNone(attempt.completed_at)
    
    def test_time_remaining_calculation(self):
        """Test time remaining calculation."""
        attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.user)
        
        remaining = attempt.time_remaining_seconds()
        self.assertIsNotNone(remaining)
        self.assertGreater(remaining, 0)
    
    def test_is_expired(self):
        """Test expiry check."""
        # Create attempt from 1 hour ago
        past_time = timezone.now() - timedelta(hours=1)
        attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.user, started_at=past_time)
        
        self.assertTrue(attempt.is_expired())


class AssignmentModelTest(TestCase):
    """Test Assignment model functionality."""
    
    def setUp(self):
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category)
        self.module = Module.objects.create(course=self.course, title='Module', position=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson', content_type='text', content_text='Lesson content', position=1)
    
    def test_assignment_creation(self):
        """Test creating assignment."""
        assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Essay Assignment',
            instructions='Write 500 words',
            max_score=100
        )
        
        self.assertEqual(assignment.lesson, self.lesson)
        self.assertEqual(assignment.max_score, 100)


class SubmissionModelTest(TestCase):
    """Test Submission model functionality."""
    
    def setUp(self):
        self.student = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category)
        self.module = Module.objects.create(course=self.course, title='Module', position=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson', content_type='text', content_text='Lesson content', position=1)
        self.assignment = Assignment.objects.create(lesson=self.lesson, title='Assignment', max_score=100)
    
    def test_submission_creation(self):
        """Test creating submission."""
        submission = Submission.objects.create(
            assignment=self.assignment,
            user=self.student,
            text='My answer'
        )
        
        self.assertEqual(submission.assignment, self.assignment)
        self.assertEqual(submission.user, self.student)
        self.assertIsNone(submission.grade)
    
    def test_submission_unique_constraint(self):
        """Test unique constraint on assignment-user pair."""
        Submission.objects.create(assignment=self.assignment, user=self.student)
        
        with self.assertRaises(Exception):
            Submission.objects.create(assignment=self.assignment, user=self.student)


# ===========================
# 🔧 Service Tests
# ===========================

class QuizServicesTest(TestCase):
    """Test quiz service functions."""
    
    def setUp(self):
        self.student = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category)
        self.module = Module.objects.create(course=self.course, title='Module', position=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson', content_type='text', content_text='Lesson content', position=1)
        self.quiz = Quiz.objects.create(lesson=self.lesson, title='Quiz', total_marks=10)
        
        # Create questions
        self.q1 = QuizQuestion.objects.create(quiz=self.quiz, question_text='Q1', question_type='mcq', marks=5)
        self.q2 = QuizQuestion.objects.create(quiz=self.quiz, question_text='Q2', question_type='mcq', marks=5)
        
        # Create options
        self.opt1_correct = QuestionOption.objects.create(question=self.q1, option_text='Correct', is_correct=True)
        self.opt1_wrong = QuestionOption.objects.create(question=self.q1, option_text='Wrong', is_correct=False)
        
        self.opt2_correct = QuestionOption.objects.create(question=self.q2, option_text='Correct', is_correct=True)
        self.opt2_wrong = QuestionOption.objects.create(question=self.q2, option_text='Wrong', is_correct=False)
    
    def test_calculate_quiz_score_full_marks(self):
        """Test calculating perfect score."""
        attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.student)
        attempt.answers = {
            str(self.q1.id): str(self.opt1_correct.id),
            str(self.q2.id): str(self.opt2_correct.id)
        }
        attempt.save()
        
        score = calculate_quiz_score(attempt)
        self.assertEqual(score, Decimal('2'))  # 2 correct answers
    
    def test_calculate_quiz_score_partial(self):
        """Test calculating partial score."""
        attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.student)
        attempt.answers = {
            str(self.q1.id): str(self.opt1_correct.id),
            str(self.q2.id): str(self.opt2_wrong.id)
        }
        attempt.save()
        
        score = calculate_quiz_score(attempt)
        self.assertEqual(score, Decimal('1'))  # 1 correct answer


class GradingServicesTest(TestCase):
    """Test grading service functions."""
    
    def setUp(self):
        self.student = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category)
        self.module = Module.objects.create(course=self.course, title='Module', position=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson', content_type='text', content_text='Lesson content', position=1)
        self.assignment = Assignment.objects.create(lesson=self.lesson, title='Assignment', max_score=100)
        self.submission = Submission.objects.create(assignment=self.assignment, user=self.student, text='My answer')
    
    def test_grade_submission(self):
        """Test grading a submission."""
        graded = grade_submission(self.submission, 85, 'Great work!')
        
        self.assertEqual(graded.grade, Decimal('85'))
        self.assertEqual(graded.feedback, 'Great work!')
        self.assertIsNotNone(graded.graded_at)
    
    def test_grade_submission_with_rubric(self):
        """Test grading with rubric."""
        rubric = Rubric.objects.create(
            assignment=self.assignment,
            total_marks=Decimal('100'),
            criteria=[
                {"key": "clarity", "label": "Clarity", "max": 50},
                {"key": "accuracy", "label": "Accuracy", "max": 50}
            ]
        )
        
        rubric_scores = {
            "clarity": 45,
            "accuracy": 48
        }
        
        graded = grade_submission_with_rubric(self.submission, rubric_scores, 'Excellent')
        
        self.assertEqual(graded.grade, Decimal('93'))
        self.assertEqual(graded.feedback, 'Excellent')


# ===========================
# 🌐 API Tests
# ===========================

class QuizAPITest(APITestCase):
    """Test quiz API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.student = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category, status='published')
        self.module = Module.objects.create(course=self.course, title='Module', position=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson', content_type='text', content_text='Lesson content', position=1)
        
        self.quiz = Quiz.objects.create(lesson=self.lesson, title='Test Quiz', total_marks=10)
        
        # Create question and options
        self.question = QuizQuestion.objects.create(quiz=self.quiz, question_text='Q1', question_type='mcq', marks=5)
        self.opt_correct = QuestionOption.objects.create(question=self.question, option_text='Correct', is_correct=True)
        self.opt_wrong = QuestionOption.objects.create(question=self.question, option_text='Wrong', is_correct=False)
        
        # Enroll student
        from enrollments.models import Enrollment
        Enrollment.objects.create(user=self.student, course=self.course, status='active')
        
        self.client.force_authenticate(user=self.student)
    
    def test_get_quiz_detail(self):
        """Test getting quiz details."""
        url = f'/api/assessments/quiz/lesson/{self.lesson.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Quiz')


class AssignmentAPITest(APITestCase):
    """Test assignment API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
        self.student = User.objects.create_user(email='student@test.com', password='testpass123')
        self.instructor = User.objects.create_user(email='instructor@test.com', password='testpass123', role='instructor')
        
        self.category = Category.objects.create(name='Tech', slug='tech')
        self.course = Course.objects.create(title='Course', instructor=self.instructor, category=self.category, status='published')
        self.module = Module.objects.create(course=self.course, title='Module', position=1)
        self.lesson = Lesson.objects.create(module=self.module, title='Lesson', content_type='text', content_text='Lesson content', position=1)
        
        self.assignment = Assignment.objects.create(lesson=self.lesson, title='Essay', max_score=100)
        
        # Enroll student
        from enrollments.models import Enrollment
        Enrollment.objects.create(user=self.student, course=self.course, status='active')
        
        self.client.force_authenticate(user=self.student)
    
    def test_get_assignment_detail(self):
        """Test getting assignment details."""
        url = f'/api/assessments/assignment/lesson/{self.lesson.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Essay')
