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
from .models import Quiz, QuizQuestion, QuestionOption, QuizAttempt
from .services import start_quiz_attempt, submit_quiz_attempt
from .services_scoring import calculate_quiz_score

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
            difficulty='easy',
            marks=5
        )
        
        self.assertEqual(question.marks, 5)


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
        self.q1 = QuizQuestion.objects.create(quiz=self.quiz, question_text='Q1', marks=5)
        self.q2 = QuizQuestion.objects.create(quiz=self.quiz, question_text='Q2', marks=5)
        
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
        self.question = QuizQuestion.objects.create(quiz=self.quiz, question_text='Q1', marks=5)
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

    def test_quiz_start_snapshots_question_evidence(self):
        response = self.client.post(f'/api/assessments/quiz/{self.quiz.id}/attempt/start/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        attempt = QuizAttempt.objects.get(id=response.data['attempt_id'])
        self.assertEqual(attempt.total_marks_snapshot, 5)
        self.assertEqual(len(attempt.question_snapshot), 1)
        self.assertEqual(
            attempt.question_snapshot[0]['question_id'],
            self.question.id
        )
        self.assertEqual(
            {
                option['option_id']: option['is_correct']
                for option in attempt.question_snapshot[0]['options']
            },
            {
                self.opt_correct.id: True,
                self.opt_wrong.id: False,
            }
        )

    def test_incremental_answer_rejects_question_outside_attempt(self):
        other_lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 2',
            content_type='text',
            content_text='Lesson content',
            position=2
        )
        other_quiz = Quiz.objects.create(lesson=other_lesson, title='Other Quiz')
        other_question = QuizQuestion.objects.create(
            quiz=other_quiz,
            question_text='Other Q',
            marks=5
        )
        other_option = QuestionOption.objects.create(
            question=other_question,
            option_text='Other',
            is_correct=True
        )
        attempt = start_quiz_attempt(self.student, self.quiz)

        response = self.client.post(
            f'/api/assessments/quiz/attempt/{attempt.id}/answer/submit/',
            {
                'question_id': other_question.id,
                'option_id': other_option.id,
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['error'],
            'Question is not part of this quiz attempt.'
        )
        attempt.refresh_from_db()
        self.assertEqual(attempt.answers, {})

    def test_incremental_answer_rejects_option_for_different_question(self):
        second_question = QuizQuestion.objects.create(
            quiz=self.quiz,
            question_text='Q2',
            marks=5
        )
        second_option = QuestionOption.objects.create(
            question=second_question,
            option_text='Second',
            is_correct=True
        )
        attempt = start_quiz_attempt(self.student, self.quiz)

        response = self.client.post(
            f'/api/assessments/quiz/attempt/{attempt.id}/answer/submit/',
            {
                'question_id': self.question.id,
                'option_id': second_option.id,
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['error'],
            'Option is not valid for this question.'
        )
        attempt.refresh_from_db()
        self.assertEqual(attempt.answers, {})

    def test_incremental_answer_saves_normalized_valid_answer(self):
        attempt = start_quiz_attempt(self.student, self.quiz)

        response = self.client.post(
            f'/api/assessments/quiz/attempt/{attempt.id}/answer/submit/',
            {
                'question_id': self.question.id,
                'option_id': self.opt_correct.id,
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        attempt.refresh_from_db()
        self.assertEqual(
            attempt.answers,
            {str(self.question.id): str(self.opt_correct.id)}
        )

    def test_batch_submit_rejects_invalid_answer_pairs_without_completing(self):
        other_lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 2',
            content_type='text',
            content_text='Lesson content',
            position=2
        )
        other_quiz = Quiz.objects.create(lesson=other_lesson, title='Other Quiz')
        other_question = QuizQuestion.objects.create(
            quiz=other_quiz,
            question_text='Other Q',
            marks=5
        )
        other_option = QuestionOption.objects.create(
            question=other_question,
            option_text='Other',
            is_correct=True
        )
        attempt = start_quiz_attempt(self.student, self.quiz)

        response = self.client.post(
            f'/api/assessments/quiz/attempt/{attempt.id}/submit/',
            {
                'answers': {
                    str(other_question.id): str(other_option.id),
                },
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['error'],
            'Question is not part of this quiz attempt.'
        )
        attempt.refresh_from_db()
        self.assertIsNone(attempt.completed_at)
        self.assertEqual(attempt.answers, {})

    def test_quiz_start_routes_reuse_single_active_attempt(self):
        canonical_response = self.client.post(f'/api/assessments/quiz/{self.quiz.id}/start/')
        alternate_response = self.client.post(f'/api/assessments/quiz/{self.quiz.id}/attempt/start/')

        self.assertEqual(canonical_response.status_code, status.HTTP_200_OK)
        self.assertEqual(alternate_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            canonical_response.data['id'],
            alternate_response.data['attempt_id']
        )
        self.assertEqual(
            QuizAttempt.objects.filter(quiz=self.quiz, user=self.student).count(),
            1
        )

    def test_quiz_start_routes_reject_retakes_after_completion(self):
        attempt = QuizAttempt.objects.create(
            quiz=self.quiz,
            user=self.student,
            completed_at=timezone.now()
        )

        canonical_response = self.client.post(f'/api/assessments/quiz/{self.quiz.id}/start/')
        alternate_response = self.client.post(f'/api/assessments/quiz/{self.quiz.id}/attempt/start/')

        self.assertEqual(canonical_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(alternate_response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(canonical_response.data['error'], 'Quiz already completed.')
        self.assertEqual(alternate_response.data['error'], 'Quiz already completed.')
        self.assertEqual(
            list(QuizAttempt.objects.filter(quiz=self.quiz, user=self.student)),
            [attempt]
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

    def test_manage_quiz_post_rejects_invalid_question_payload_without_creating_quiz(self):
        self.client.force_authenticate(user=self.instructor)
        cases = [
            (
                'blank text',
                {
                    'questions': [
                        {
                            'text': '',
                            'type': 'mcq',
                            'marks': 1,
                            'options': [
                                {'text': 'Correct', 'is_correct': True},
                                {'text': 'Wrong', 'is_correct': False},
                            ],
                        }
                    ],
                },
                'questions[0].text is required.',
            ),
            (
                'unsupported type',
                {
                    'questions': [
                        {
                            'text': 'Pick one',
                            'type': 'essay',
                            'marks': 1,
                            'options': [
                                {'text': 'Correct', 'is_correct': True},
                                {'text': 'Wrong', 'is_correct': False},
                            ],
                        }
                    ],
                },
                'questions[0].type must be mcq.',
            ),
            (
                'too few options',
                {
                    'questions': [
                        {
                            'text': 'Pick one',
                            'type': 'mcq',
                            'marks': 1,
                            'options': [{'text': 'Correct', 'is_correct': True}],
                        }
                    ],
                },
                'questions[0].options must contain at least 2 options.',
            ),
            (
                'no correct option',
                {
                    'questions': [
                        {
                            'text': 'Pick one',
                            'type': 'mcq',
                            'marks': 1,
                            'options': [
                                {'text': 'Wrong A', 'is_correct': False},
                                {'text': 'Wrong B', 'is_correct': False},
                            ],
                        }
                    ],
                },
                'questions[0] must have exactly one correct option.',
            ),
            (
                'multiple correct options',
                {
                    'questions': [
                        {
                            'text': 'Pick one',
                            'type': 'mcq',
                            'marks': 1,
                            'options': [
                                {'text': 'Correct A', 'is_correct': True},
                                {'text': 'Correct B', 'is_correct': True},
                            ],
                        }
                    ],
                },
                'questions[0] must have exactly one correct option.',
            ),
            (
                'invalid marks',
                {
                    'questions': [
                        {
                            'text': 'Pick one',
                            'type': 'mcq',
                            'marks': 0,
                            'options': [
                                {'text': 'Correct', 'is_correct': True},
                                {'text': 'Wrong', 'is_correct': False},
                            ],
                        }
                    ],
                },
                'questions[0].marks must be at least 1.',
            ),
            (
                'invalid passing percentage',
                {
                    'passing_percentage': 101,
                    'questions': [
                        {
                            'text': 'Pick one',
                            'type': 'mcq',
                            'marks': 1,
                            'options': [
                                {'text': 'Correct', 'is_correct': True},
                                {'text': 'Wrong', 'is_correct': False},
                            ],
                        }
                    ],
                },
                'passing_percentage must be at most 100.',
            ),
            (
                'invalid time limit',
                {
                    'time_limit_minutes': -1,
                    'questions': [
                        {
                            'text': 'Pick one',
                            'type': 'mcq',
                            'marks': 1,
                            'options': [
                                {'text': 'Correct', 'is_correct': True},
                                {'text': 'Wrong', 'is_correct': False},
                            ],
                        }
                    ],
                },
                'time_limit_minutes must be at least 1.',
            ),
        ]

        for label, payload, expected_error in cases:
            with self.subTest(label):
                response = self.client.post(self.url, payload, format='json')

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIn(expected_error, response.data['errors'])
                self.assertFalse(Quiz.objects.filter(lesson=self.lesson).exists())
                self.assertEqual(QuizQuestion.objects.count(), 0)
                self.assertEqual(QuestionOption.objects.count(), 0)

    def test_manage_quiz_post_rejects_invalid_replacement_without_changing_existing_quiz(self):
        quiz = Quiz.objects.create(
            lesson=self.lesson,
            title='Original Quiz',
            passing_percentage=60,
            time_limit_minutes=10,
            total_marks=2
        )
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text='Original question',
            marks=2
        )
        QuestionOption.objects.create(question=question, option_text='Correct', is_correct=True)
        QuestionOption.objects.create(question=question, option_text='Wrong', is_correct=False)
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(
            self.url,
            {
                'title': 'Invalid Replacement',
                'passing_percentage': 80,
                'time_limit_minutes': 30,
                'questions': [
                    {
                        'text': 'Replacement question',
                        'type': 'mcq',
                        'marks': 2,
                        'options': [
                            {'text': 'Wrong A', 'is_correct': False},
                            {'text': 'Wrong B', 'is_correct': False},
                        ],
                    }
                ],
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('questions[0] must have exactly one correct option.', response.data['errors'])
        quiz.refresh_from_db()
        self.assertEqual(quiz.title, 'Original Quiz')
        self.assertEqual(quiz.passing_percentage, 60)
        self.assertEqual(quiz.time_limit_minutes, 10)
        self.assertEqual(quiz.total_marks, 2)
        question.refresh_from_db()
        self.assertEqual(question.question_text, 'Original question')
        self.assertEqual(question.options.count(), 2)

    def test_manage_quiz_post_rejects_true_false_question_type(self):
        self.client.force_authenticate(user=self.instructor)

        response = self.client.post(
            self.url,
            {
                'title': 'Rejected True False Quiz',
                'questions': [
                    {
                        'text': 'The sky is blue.',
                        'type': 'tf',
                        'marks': 1,
                        'options': [
                            {'text': 'True', 'is_correct': True},
                            {'text': 'False', 'is_correct': False},
                        ],
                    }
                ],
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('questions[0].type must be mcq.', response.data['errors'])
        self.assertFalse(Quiz.objects.filter(lesson=self.lesson).exists())

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
