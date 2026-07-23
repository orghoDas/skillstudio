from django.test import TestCase
from django.urls import resolve
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from datetime import timedelta

from courses.models import Course, Module, Lesson, Category
from enrollments.models import Enrollment
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
        self.assertEqual(score, Decimal('10'))  # Uses configured question marks
        attempt.refresh_from_db()
        self.assertTrue(attempt.passed)
    
    def test_calculate_quiz_score_partial(self):
        """Test calculating partial score."""
        attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.student)
        attempt.answers = {
            str(self.q1.id): str(self.opt1_correct.id),
            str(self.q2.id): str(self.opt2_wrong.id)
        }
        attempt.save()
        
        score = calculate_quiz_score(attempt)
        self.assertEqual(score, Decimal('5'))  # Uses configured question marks
        attempt.refresh_from_db()
        self.assertTrue(attempt.passed)

    def test_submit_paths_use_same_quiz_scoring(self):
        answers = {
            str(self.q1.id): str(self.opt1_correct.id),
            str(self.q2.id): str(self.opt2_wrong.id)
        }
        service_attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.student)
        legacy_attempt = QuizAttempt.objects.create(quiz=self.quiz, user=self.instructor)

        submit_quiz_attempt(service_attempt, answers)
        legacy_attempt.answers = answers
        legacy_attempt.save(update_fields=['answers'])
        legacy_score = calculate_quiz_score(legacy_attempt)

        service_attempt.refresh_from_db()
        legacy_attempt.refresh_from_db()
        self.assertEqual(service_attempt.score, legacy_score)
        self.assertEqual(legacy_attempt.score, Decimal('5'))

    def test_quiz_submit_url_resolves_to_single_batch_submit_view(self):
        match = resolve('/api/assessments/quiz/attempt/123/submit/')

        self.assertEqual(match.func.view_class.__name__, 'SubmitQuizView')


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
        
        Enrollment.objects.create(user=self.student, course=self.course, status='active')
        
        self.client.force_authenticate(user=self.student)
    
    def test_get_quiz_detail(self):
        """Test getting quiz details."""
        url = f'/api/assessments/quiz/lesson/{self.lesson.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Test Quiz')

    def test_alternate_quiz_start_requires_active_enrollment(self):
        unenrolled_student = User.objects.create_user(
            email='unenrolled@test.com',
            password='testpass123'
        )
        self.client.force_authenticate(user=unenrolled_student)

        response = self.client.post(f'/api/assessments/quiz/{self.quiz.id}/attempt/start/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            QuizAttempt.objects.filter(quiz=self.quiz, user=unenrolled_student).exists()
        )

    def test_alternate_quiz_start_rejects_unpublished_quiz(self):
        self.quiz.is_published = False
        self.quiz.save(update_fields=['is_published'])

        response = self.client.post(f'/api/assessments/quiz/{self.quiz.id}/attempt/start/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(
            QuizAttempt.objects.filter(quiz=self.quiz, user=self.student).exists()
        )

    def test_alternate_quiz_start_allows_enrolled_student(self):
        response = self.client.post(f'/api/assessments/quiz/{self.quiz.id}/attempt/start/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('attempt_id', response.data)
        self.assertTrue(
            QuizAttempt.objects.filter(
                quiz=self.quiz,
                user=self.student,
                completed_at__isnull=True,
            ).exists()
        )

    def test_quiz_question_analytics_uses_current_option_schema(self):
        QuizAttempt.objects.create(
            quiz=self.quiz,
            user=self.student,
            answers={str(self.question.id): str(self.opt_wrong.id)}
        )
        other_student = User.objects.create_user(
            email='other-student@test.com',
            password='testpass123'
        )
        QuizAttempt.objects.create(
            quiz=self.quiz,
            user=other_student,
            answers={str(self.question.id): str(self.opt_correct.id)}
        )
        QuizAttempt.objects.create(
            quiz=self.quiz,
            user=self.instructor,
            answers={}
        )
        self.client.force_authenticate(user=self.instructor)

        response = self.client.get(f'/api/assessments/analytics/quiz/{self.quiz.id}/questions/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['question_id'], self.question.id)
        self.assertEqual(response.data[0]['attempts'], 2)
        self.assertEqual(response.data[0]['wrong_attempts'], 1)
        self.assertEqual(response.data[0]['wrong_ratio'], 0.5)


class ManageQuizAPITest(APITestCase):
    """Test instructor quiz management endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            email='student-manage@test.com',
            password='testpass123',
            role='student'
        )
        self.instructor = User.objects.create_user(
            email='instructor-manage@test.com',
            password='testpass123',
            role='instructor'
        )
        self.other_instructor = User.objects.create_user(
            email='other-instructor-manage@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name='Management', slug='management')
        self.course = Course.objects.create(
            title='Managed Course',
            instructor=self.instructor,
            category=self.category,
            status='draft'
        )
        self.module = Module.objects.create(course=self.course, title='Module', position=1)
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Managed Lesson',
            content_type='quiz',
            content_text='Quiz lesson',
            position=1
        )
        self.url = f'/api/assessments/quiz/lesson/{self.lesson.id}/manage/'

    def test_manage_quiz_get_does_not_create_missing_quiz(self):
        self.client.force_authenticate(user=self.instructor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], 'Quiz not found for this lesson.')
        self.assertFalse(Quiz.objects.filter(lesson=self.lesson).exists())

    def test_manage_quiz_get_returns_existing_quiz(self):
        quiz = Quiz.objects.create(
            lesson=self.lesson,
            title='Existing Quiz',
            passing_percentage=70
        )
        self.client.force_authenticate(user=self.instructor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], quiz.id)
        self.assertEqual(response.data['title'], 'Existing Quiz')

    def test_manage_quiz_post_explicitly_creates_quiz(self):
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(
            self.url,
            {
                'title': 'Created Explicitly',
                'passing_percentage': 80,
                'questions': [
                    {
                        'text': 'Question 1',
                        'type': 'mcq',
                        'marks': 2,
                        'options': [
                            {'text': 'Correct', 'is_correct': True},
                            {'text': 'Wrong', 'is_correct': False},
                        ],
                    }
                ],
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        quiz = Quiz.objects.get(lesson=self.lesson)
        self.assertEqual(quiz.title, 'Created Explicitly')
        self.assertEqual(quiz.total_marks, 2)
        self.assertEqual(quiz.questions.count(), 1)

    def test_manage_quiz_get_rejects_non_owner_without_creating_quiz(self):
        self.client.force_authenticate(user=self.other_instructor)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Quiz.objects.filter(lesson=self.lesson).exists())

    def test_manage_quiz_post_rejects_question_replacement_after_attempts_exist(self):
        quiz = Quiz.objects.create(lesson=self.lesson, title='Attempted Quiz')
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text='Original question',
            question_type='mcq',
            marks=3
        )
        correct_option = QuestionOption.objects.create(
            question=question,
            option_text='Original correct',
            is_correct=True
        )
        QuizAttempt.objects.create(
            quiz=quiz,
            user=self.student,
            answers={str(question.id): str(correct_option.id)}
        )
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(
            self.url,
            {
                'title': 'Replacement Attempt',
                'questions': [
                    {
                        'text': 'Replacement question',
                        'type': 'mcq',
                        'marks': 1,
                        'options': [{'text': 'New correct', 'is_correct': True}],
                    }
                ],
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('cannot be replaced after attempts exist', response.data['error'])
        quiz.refresh_from_db()
        self.assertEqual(quiz.title, 'Attempted Quiz')
        self.assertEqual(quiz.questions.count(), 1)
        question.refresh_from_db()
        self.assertEqual(question.question_text, 'Original question')
        self.assertTrue(QuestionOption.objects.filter(id=correct_option.id).exists())
        self.assertEqual(
            QuizAttempt.objects.get(quiz=quiz, user=self.student).answers,
            {str(question.id): str(correct_option.id)}
        )

    def test_manage_quiz_post_allows_settings_update_after_attempts_exist(self):
        quiz = Quiz.objects.create(
            lesson=self.lesson,
            title='Attempted Quiz',
            passing_percentage=50,
            time_limit_minutes=15
        )
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text='Original question',
            question_type='mcq',
            marks=3
        )
        QuizAttempt.objects.create(quiz=quiz, user=self.student)
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(
            self.url,
            {
                'title': 'Settings Only',
                'passing_percentage': 65,
                'time_limit_minutes': 20,
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        quiz.refresh_from_db()
        self.assertEqual(quiz.title, 'Settings Only')
        self.assertEqual(quiz.passing_percentage, 65)
        self.assertEqual(quiz.time_limit_minutes, 20)
        self.assertTrue(QuizQuestion.objects.filter(id=question.id).exists())


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
        
        Enrollment.objects.create(user=self.student, course=self.course, status='active')
        
        self.client.force_authenticate(user=self.student)
    
    def test_get_assignment_detail(self):
        """Test getting assignment details."""
        url = f'/api/assessments/assignment/lesson/{self.lesson.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Essay')

    def test_submit_assignment_by_lesson_uses_existing_assignment(self):
        url = f'/api/assessments/assignment/lesson/{self.lesson.id}/submit/'

        response = self.client.post(
            url,
            {'text': 'My assignment answer'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Assignment submitted successfully')
        self.assertEqual(
            Submission.objects.get(assignment=self.assignment, user=self.student).text,
            'My assignment answer'
        )

    def test_submit_assignment_by_lesson_does_not_create_missing_assignment(self):
        lesson_without_assignment = Lesson.objects.create(
            module=self.module,
            title='Lesson Without Assignment',
            content_type='assignment',
            content_text='Do not turn this into curriculum data',
            position=2
        )
        url = f'/api/assessments/assignment/lesson/{lesson_without_assignment.id}/submit/'

        response = self.client.post(
            url,
            {'text': 'Trying to create assignment implicitly'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['error'], 'Assignment not found for this lesson.')
        self.assertFalse(Assignment.objects.filter(lesson=lesson_without_assignment).exists())
        self.assertFalse(
            Submission.objects.filter(
                user=self.student,
                text='Trying to create assignment implicitly'
            ).exists()
        )
