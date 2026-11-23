from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from random import Random
from unittest.mock import patch
from datetime import timedelta

from accounts.models import Profile
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
            total_marks=10,
            passing_marks=5,
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

    def test_expired_active_attempt_is_graded_and_counts_toward_limit(self):
        first = start_exam_attempt(self.exam, self.student)
        first.started_at = timezone.now() - timedelta(hours=2)
        first.save(update_fields=['started_at'])

        second = start_exam_attempt(self.exam, self.student)

        first.refresh_from_db()
        self.assertEqual(first.status, 'completed')
        self.assertEqual(first.score, Decimal('0.00'))
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
            total_marks=1,
            passing_marks=1,
            duration_minutes=60,
            status='published',
            created_by=self.instructor
        )
        question = QuestionBank.objects.create(
            course=self.course, question_text='Q1',
            options=[{'text': 'A', 'is_correct': True}, {'text': 'B', 'is_correct': False}],
        )
        self.exam.questions.add(question)
        
        # Enroll student
        from enrollments.models import Enrollment
        Enrollment.objects.create(user=self.student, course=self.course, status='active')
        
        self.client.force_authenticate(user=self.student)
    
    def test_get_course_exams(self):
        """Test getting exams for a course."""
        url = f'/api/exams/course/{self.course.id}/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_attempt_history_uses_two_pages_and_keeps_owner_scope(self):
        ExamAttempt.objects.bulk_create([
            ExamAttempt(exam=self.exam, user=self.student, attempt_number=index, status='completed')
            for index in range(1, 22)
        ])
        ExamAttempt.objects.create(exam=self.exam, user=self.instructor, status='completed')
        url = f'/api/exams/{self.exam.pk}/attempts/'
        first = self.client.get(url)
        second = self.client.get(f'{url}?page=2')
        self.assertEqual(first.data['count'], 21)
        self.assertEqual(len(first.data['results']), 20)
        self.assertIsNotNone(first.data['next'])
        self.assertIsNotNone(second.data['previous'])
        self.assertEqual([item['attempt_number'] for item in second.data['results']], [1])

    def test_creator_name_is_returned_or_null_on_exam_and_question_detail(self):
        Profile.objects.update_or_create(
            user=self.instructor, defaults={'first_name': 'Asha', 'last_name': 'Rahman'},
        )
        question = self.exam.questions.get()
        question.created_by = self.instructor
        question.save(update_fields=['created_by'])
        self.client.force_authenticate(self.instructor)
        for url, item in (
            (f'/api/exams/{self.exam.pk}/', self.exam),
            (f'/api/exams/questions/{question.pk}/', question),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['created_by_name'], 'Asha Rahman')
                item.created_by = None
                item.save(update_fields=['created_by'])
                self.assertIsNone(self.client.get(url).data['created_by_name'])

    def test_exam_start_and_instructor_attempt_list_return_student_name(self):
        Profile.objects.filter(user=self.student).delete()
        response = self.client.post(f'/api/exams/{self.exam.pk}/start/')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['user_name'], 'SkillStudio learner')

        Profile.objects.update_or_create(user=self.student, defaults={'full_name': 'Exam Student'})
        self.client.force_authenticate(self.instructor)
        response = self.client.get(f'/api/exams/{self.exam.pk}/all-attempts/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['results'][0]['user_name'], 'Exam Student')

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
            total_marks=6,
            passing_marks=3,
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
        # Questions are only shown during an attempt (EXM-01).
        self.assertEqual(self.client.post(f'/api/exams/{self.exam.id}/start/').status_code, status.HTTP_201_CREATED)

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

    def test_randomized_order_is_saved_and_reused_for_bank_and_custom_questions(self):
        self.exam.randomize_questions = True
        self.exam.save(update_fields=['randomize_questions'])
        self.client.force_authenticate(self.student)
        base = f'/api/exams/{self.exam.pk}/'
        original = [self.question.pk, 'custom_0']
        seed = next(str(value) for value in range(10) if Random(str(value)).randrange(2) == 0)
        expected = original[::-1]
        with patch('exams.services.token_hex', return_value=seed):
            started = self.client.post(f'{base}start/')
        self.assertEqual(started.status_code, 201, started.data)
        attempt = ExamAttempt.objects.get(pk=started.data['id'])
        self.assertEqual(attempt.snapshot['question_order_seed'], seed)
        self.assertEqual([q['id'] for q in attempt.snapshot['questions']], expected)
        with patch('exams.services.token_hex') as new_seed:
            self.assertEqual(self.client.post(f'{base}start/').data['id'], attempt.pk)
        new_seed.assert_not_called()
        for url in (base, f'{base}?attempt={attempt.pk}'):
            self.assertEqual(self.client.get(url).data['question_order'], expected)

    def test_result_routes_gate_question_review_and_delayed_grades(self):
        self.client.force_authenticate(self.student)
        base = f'/api/exams/{self.exam.pk}/'
        attempt = self.client.post(f'{base}start/').data
        result_url = f"/api/exams/attempt/{attempt['id']}/result/"
        submitted = self.client.post(f'{base}submit/', {
            'attempt_id': attempt['id'], 'answers': {str(self.question.pk): 1},
        }, format='json')
        self.assertEqual(submitted.status_code, 200, submitted.data)
        self.assertEqual(submitted.data['result']['question_results'], {})
        self.assertEqual(self.client.get(result_url).data['question_results'], {})
        self.assertEqual(self.client.get(f'{base}attempts/').data['results'][0]['result']['question_results'], {})

        self.exam.show_correct_answers = True
        self.exam.save(update_fields=['show_correct_answers'])
        detail = self.client.get(result_url).data
        self.assertEqual(detail['question_results'][str(self.question.pk)]['correct_option'], 1)
        self.assertEqual(detail['question_results'][str(self.question.pk)]['selected_option'], 1)
        self.assertEqual(detail['question_results']['custom_0']['correct_option'], 1)
        history = self.client.get(f'{base}attempts/').data['results'][0]
        self.assertEqual(history['result']['question_results'], detail['question_results'])
        retried = self.client.post(f'{base}submit/', {
            'attempt_id': attempt['id'], 'answers': {},
        }, format='json')
        self.assertEqual(retried.data['result']['question_results'], detail['question_results'])

        self.exam.show_results_immediately = False
        self.exam.save(update_fields=['show_results_immediately'])
        self.assertEqual(self.client.get(result_url).status_code, 403)
        history = self.client.get(f'{base}attempts/').data['results'][0]
        self.assertIsNone(history['score'])
        self.assertIsNone(history['result'])
        retried = self.client.post(f'{base}submit/', {
            'attempt_id': attempt['id'], 'answers': {},
        }, format='json')
        self.assertIsNone(retried.data['score'])
        self.assertNotIn('result', retried.data)
        self.client.force_authenticate(self.instructor)
        self.assertEqual(self.client.get(result_url).data['question_results'], detail['question_results'])

    def test_analytics_use_grades_and_include_custom_questions_and_zero_scores(self):
        first = start_exam_attempt(self.exam, self.student)
        submit_exam_attempt(first, {str(self.question.pk): 1, 'custom_0': 'B'})
        second = start_exam_attempt(self.exam, self.other_student)
        submit_exam_attempt(second, {str(self.question.pk): '3', 'custom_0': None})
        self.question.options.reverse()
        self.question.save(update_fields=['options'])
        self.client.force_authenticate(self.instructor)
        response = self.client.get(f'/api/exams/{self.exam.pk}/analytics/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['average_score'], 3)
        self.assertEqual(response.data['pass_rate'], 50)
        rows = {row['question_id']: row for row in response.data['question_analytics']}
        self.assertEqual(rows[self.question.pk]['correct_percentage'], 50)
        self.assertEqual(rows['custom_0']['correct_percentage'], 100)
        self.assertEqual(rows['custom_0']['total_attempts'], 1)

    def test_foreign_bank_questions_are_rejected_on_create_update_publish_and_start(self):
        foreign = QuestionBank.objects.create(
            course=self.other_course, question_text='Foreign bank question',
            options=[{'text': 'A', 'is_correct': True}, {'text': 'B', 'is_correct': False}],
        )
        base = f'/api/exams/{self.exam.pk}/'
        self.client.force_authenticate(self.instructor)
        created = self.client.post('/api/exams/', {
            'course': self.course.pk, 'title': 'New exam', 'duration_minutes': 10,
            'questions': [foreign.pk],
        }, format='json')
        updated = self.client.patch(base, {'questions': [foreign.pk]}, format='json')
        for response in (created, updated):
            self.assertEqual(response.status_code, 400, response.data)
            self.assertIn('questions', response.data['fields'])

        Course.objects.filter(pk=self.course.pk).update(status='draft')
        self.exam.questions.add(foreign)
        rejected = self.client.post(f'{base}publish/')
        self.assertEqual((rejected.status_code, rejected.data['code']), (400, 'invalid_question_course'))
        self.client.force_authenticate(self.student)
        rejected = self.client.post(f'{base}start/')
        self.assertEqual((rejected.status_code, rejected.data['code']), (409, 'invalid_question_course'))

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
