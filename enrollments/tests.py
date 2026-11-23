from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from decimal import Decimal
from datetime import timedelta

from accounts.models import Profile
from courses.models import Course, Module, Lesson, Category
from .models import Enrollment, LessonProgress, Wishlist
from .services import (
    mark_lesson_completed,
    check_and_complete_course,
    auto_complete_lesson,
    evaluate_and_complete_enrollment,
    get_resume_lesson,
    update_lesson_watch_progress,
)

User = get_user_model()


# ===========================
# 🧪 Model Tests
# ===========================

class EnrollmentModelTest(TestCase):
    """Test Enrollment model functionality."""
    
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
            description='Test Description',
            instructor=self.instructor,
            category=self.category,
            price=Decimal('49.99'),
            status='published'
        )
    
    def test_enrollment_creation(self):
        """Test creating an enrollment."""
        enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course
        )
        
        self.assertEqual(enrollment.user, self.user)
        self.assertEqual(enrollment.course, self.course)
        self.assertEqual(enrollment.status, 'active')
        self.assertFalse(enrollment.is_completed)
        self.assertIsNotNone(enrollment.enrolled_at)
    
    def test_enrollment_unique_constraint(self):
        """Test that user can't enroll in same course twice."""
        Enrollment.objects.create(user=self.user, course=self.course)
        
        with self.assertRaises(Exception):
            Enrollment.objects.create(user=self.user, course=self.course)
    
    def test_enrollment_str_representation(self):
        """Test string representation of enrollment."""
        enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course
        )
        
        expected = f"{self.user.email} - {self.course.title}"
        self.assertEqual(str(enrollment), expected)


class LessonProgressModelTest(TestCase):
    """Test LessonProgress model functionality."""
    
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
            description='Test Description',
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
            content_type='video',
            video_url='https://example.com/video.mp4',
            duration_seconds=600,
            position=1
        )
        
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course
        )
    
    def test_lesson_progress_creation(self):
        """Test creating lesson progress."""
        progress = LessonProgress.objects.create(
            enrollment=self.enrollment,
            user=self.user,
            lesson=self.lesson,
            watch_time=300
        )
        
        self.assertEqual(progress.enrollment, self.enrollment)
        self.assertEqual(progress.user, self.user)
        self.assertEqual(progress.lesson, self.lesson)
        self.assertEqual(progress.watch_time, 300)
        self.assertFalse(progress.is_completed)
    
    def test_lesson_progress_unique_constraint(self):
        """Test unique constraint on enrollment-lesson pair."""
        LessonProgress.objects.create(
            enrollment=self.enrollment,
            user=self.user,
            lesson=self.lesson
        )
        
        with self.assertRaises(Exception):
            LessonProgress.objects.create(
                enrollment=self.enrollment,
                user=self.user,
                lesson=self.lesson
            )


class WishlistModelTest(TestCase):
    """Test Wishlist model functionality."""
    
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
            description='Test Description',
            instructor=self.instructor,
            category=self.category,
            status='published'
        )
    
    def test_wishlist_creation(self):
        """Test adding course to wishlist."""
        wishlist = Wishlist.objects.create(
            user=self.user,
            course=self.course
        )
        
        self.assertEqual(wishlist.user, self.user)
        self.assertEqual(wishlist.course, self.course)
        self.assertIsNotNone(wishlist.added_at)
    
    def test_wishlist_unique_constraint(self):
        """Test that course can't be added to wishlist twice."""
        Wishlist.objects.create(user=self.user, course=self.course)
        
        with self.assertRaises(Exception):
            Wishlist.objects.create(user=self.user, course=self.course)


# ===========================
# 🔧 Service Tests
# ===========================

class EnrollmentServicesTest(TestCase):
    """Test enrollment service functions."""
    
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
        
        self.lesson1 = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            content_type='video',
            video_url='https://example.com/video1.mp4',
            duration_seconds=600,
            position=1
        )
        
        self.lesson2 = Lesson.objects.create(
            module=self.module,
            title='Lesson 2',
            content_type='video',
            video_url='https://example.com/video2.mp4',
            duration_seconds=600,
            position=2
        )
        
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course
        )
    
    def test_mark_lesson_completed(self):
        """Test marking a lesson as completed."""
        progress = mark_lesson_completed(self.enrollment, self.lesson1)
        
        self.assertTrue(progress.is_completed)
        self.assertIsNotNone(progress.completed_at)
    
    def test_auto_complete_lesson(self):
        """Test auto-completion when watch threshold reached."""
        progress = LessonProgress.objects.create(
            enrollment=self.enrollment,
            user=self.user,
            lesson=self.lesson1,
            watch_time=500  # 500/600 = 83% > 80% threshold
        )
        
        should_complete = auto_complete_lesson(progress)
        self.assertTrue(should_complete)
    
    def test_auto_complete_lesson_not_reached(self):
        """Test auto-completion when watch threshold not reached."""
        progress = LessonProgress.objects.create(
            enrollment=self.enrollment,
            user=self.user,
            lesson=self.lesson1,
            watch_time=300  # 300/600 = 50% < 80% threshold
        )
        
        should_complete = auto_complete_lesson(progress)
        self.assertFalse(should_complete)
    
    def test_check_and_complete_course(self):
        """Test course auto-completion when all lessons done."""
        # Complete all lessons
        mark_lesson_completed(self.enrollment, self.lesson1)
        mark_lesson_completed(self.enrollment, self.lesson2)
        
        # Check if course is completed
        result = check_and_complete_course(self.enrollment)
        
        self.assertTrue(result)
        self.enrollment.refresh_from_db()
        self.assertTrue(self.enrollment.is_completed)
        self.assertEqual(self.enrollment.status, 'completed')

    def test_free_lessons_do_not_satisfy_required_paid_lessons(self):
        """Completing preview lessons must not complete the course."""
        free_lesson1 = Lesson.objects.create(
            module=self.module,
            title='Preview 1',
            content_type='video',
            duration_seconds=0,
            position=3,
            is_free=True
        )
        free_lesson2 = Lesson.objects.create(
            module=self.module,
            title='Preview 2',
            content_type='video',
            duration_seconds=0,
            position=4,
            is_free=True
        )

        mark_lesson_completed(self.enrollment, free_lesson1)
        mark_lesson_completed(self.enrollment, free_lesson2)

        result = check_and_complete_course(self.enrollment)

        self.assertFalse(result)
        self.enrollment.refresh_from_db()
        self.assertFalse(self.enrollment.is_completed)
        self.assertEqual(self.enrollment.status, 'active')

    def test_completion_evaluation_is_idempotent(self):
        mark_lesson_completed(self.enrollment, self.lesson1)
        mark_lesson_completed(self.enrollment, self.lesson2)

        first = evaluate_and_complete_enrollment(self.enrollment.id)
        self.enrollment.refresh_from_db()
        completed_at = self.enrollment.completed_at
        second = evaluate_and_complete_enrollment(self.enrollment.id)
        self.enrollment.refresh_from_db()

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(self.enrollment.completed_at, completed_at)
    
    def test_get_resume_lesson(self):
        """Test getting the next lesson to resume."""
        # Complete first lesson
        mark_lesson_completed(self.enrollment, self.lesson1)
        
        # Should return second lesson
        next_lesson = get_resume_lesson(self.enrollment)
        self.assertEqual(next_lesson, self.lesson2)
    
# ===========================
# 🌐 API Tests
# ===========================

class EnrollmentAPITest(APITestCase):
    """Test enrollment API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
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
            price=Decimal('0.00'),
            is_free=True,
            status='published'
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1',
            position=1
        )
        self.lesson1 = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            content_type='video',
            duration_seconds=600,
            position=1
        )
        self.lesson2 = Lesson.objects.create(
            module=self.module,
            title='Lesson 2',
            content_type='video',
            duration_seconds=600,
            position=2
        )
        
        self.client.force_authenticate(user=self.user)

    def test_enrollment_lists_and_detail_include_thumbnail_and_instructor_name(self):
        thumbnail = 'https://example.test/enrollment.png'
        self.course.thumbnail = thumbnail
        self.course.save(update_fields=['thumbnail'])
        Profile.objects.update_or_create(user=self.instructor, defaults={'full_name': 'Instructor Display Name'})
        enrollment = Enrollment.objects.create(user=self.user, course=self.course)

        for url in ('/api/enrollments/', '/api/enrollments/my-enrollments/', '/api/enrollments/my-learning/'):
            with self.subTest(url=url):
                result = self.client.get(url)
                self.assertEqual(result.status_code, 200, result.data)
                row = result.data['results'][0]
                self.assertEqual(row['course_thumbnail'], thumbnail)
                self.assertEqual(row['instructor_name'], 'Instructor Display Name')
                self.assertEqual(row['course']['thumbnail'], thumbnail)

        result = self.client.get(f'/api/enrollments/enrollments/{enrollment.pk}/')
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['course']['instructor']['name'], 'Instructor Display Name')

    def test_completed_course_with_null_thumbnail_and_no_profile_keeps_both_fields(self):
        Profile.objects.filter(user=self.instructor).delete()
        Enrollment.objects.create(
            user=self.user, course=self.course, status='completed', is_completed=True, completed_at=timezone.now(),
        )

        result = self.client.get('/api/enrollments/completed-courses/')
        self.assertEqual(result.status_code, 200, result.data)
        row = result.data['results'][0]
        self.assertIsNone(row['course_thumbnail'])
        self.assertEqual(row['instructor_name'], 'Instructor')
    
    def test_enroll_in_course(self):
        """Test enrolling in a course."""
        url = '/api/enrollments/enroll/'
        data = {'course_id': self.course.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Enrollment.objects.filter(user=self.user, course=self.course).exists())
    
    def test_paid_enroll_debits_canonical_wallet_and_credits_instructor(self):
        """Paid enrollment moves money through the canonical wallet ledger only."""
        from students.models import Wallet

        paid_course = Course.objects.create(
            title='Paid Course', instructor=self.instructor, category=self.category,
            price=Decimal('100.00'), is_free=False, status='published',
        )
        student_wallet = Wallet.objects.create(user=self.user, balance=Decimal('150.00'))

        response = self.client.post(
            '/api/enrollments/enroll/', {'course_id': paid_course.id}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        student_wallet.refresh_from_db()
        self.assertEqual(student_wallet.balance, Decimal('50.00'))  # 150 - 100
        self.assertEqual(
            student_wallet.transactions.filter(transaction_type='debit').count(), 1
        )

        # Instructor earns price minus the 10% platform fee, in their own wallet.
        instructor_wallet = Wallet.objects.get(user=self.instructor)
        self.assertEqual(instructor_wallet.balance, Decimal('90.00'))
        self.assertEqual(
            instructor_wallet.transactions.filter(transaction_type='credit').count(), 1
        )

    def test_paid_enroll_insufficient_balance_is_rejected(self):
        """Insufficient funds blocks enrollment and moves no money."""
        from students.models import Wallet

        paid_course = Course.objects.create(
            title='Pricey Course', instructor=self.instructor, category=self.category,
            price=Decimal('100.00'), is_free=False, status='published',
        )
        Wallet.objects.create(user=self.user, balance=Decimal('10.00'))

        response = self.client.post(
            '/api/enrollments/enroll/', {'course_id': paid_course.id}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(
            Enrollment.objects.filter(user=self.user, course=paid_course).exists()
        )

    def test_enroll_in_nonexistent_course(self):
        """Test enrolling in a non-existent course."""
        url = '/api/enrollments/enroll/'
        data = {'course_id': 99999}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_enrollments(self):
        """Test listing user enrollments."""
        Enrollment.objects.create(user=self.user, course=self.course)
        
        url = '/api/enrollments/my-enrollments/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
    
    def test_cancel_enrollment(self):
        """Test canceling an enrollment."""
        enrollment = Enrollment.objects.create(user=self.user, course=self.course)
        
        url = f'/api/enrollments/enrollments/{enrollment.id}/cancel/'
        response = self.client.patch(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, 'canceled')

    def test_course_progress_get_does_not_complete_enrollment(self):
        enrollment = Enrollment.objects.create(user=self.user, course=self.course)
        mark_lesson_completed(enrollment, self.lesson1)
        mark_lesson_completed(enrollment, self.lesson2)

        response = self.client.get(f'/api/enrollments/courses/{self.course.id}/progress/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['progress_percentage'], 100.0)
        enrollment.refresh_from_db()
        self.assertFalse(enrollment.is_completed)
        self.assertEqual(enrollment.status, 'active')

    def test_lesson_progress_get_does_not_create_progress_row(self):
        Enrollment.objects.create(user=self.user, course=self.course)

        response = self.client.get(f'/api/enrollments/lessons/{self.lesson1.id}/progress/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['id'])
        self.assertEqual(response.data['watch_time'], 0)
        self.assertFalse(response.data['is_completed'])
        self.assertIsNone(response.data['started_at'])
        self.assertFalse(
            LessonProgress.objects.filter(user=self.user, lesson=self.lesson1).exists()
        )

    def test_lesson_watch_time_rejects_absolute_update(self):
        Enrollment.objects.create(user=self.user, course=self.course)

        response = self.client.patch(
            f'/api/enrollments/lessons/{self.lesson1.id}/watch-time/',
            {'watch_time': 500},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['detail'],
            'Use watch_time_delta; absolute watch_time updates are not accepted.'
        )
        self.assertEqual(response.data['code'], 'validation_error')
        self.assertFalse(
            LessonProgress.objects.filter(user=self.user, lesson=self.lesson1).exists()
        )

    def test_first_report_and_repeated_reports_cannot_inflate_time(self):
        from unittest.mock import patch

        enrollment = Enrollment.objects.create(user=self.user, course=self.course)
        url = f'/api/enrollments/lessons/{self.lesson1.id}/watch-time/'
        start = timezone.now()
        for seconds, expected in ((0, 15), (0, 0), (1, 1), (2, 1)):
            with patch('django.utils.timezone.now', return_value=start + timedelta(seconds=seconds)):
                response = self.client.patch(url, {'watch_time_delta': 60}, format='json')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['accepted_delta'], expected)
        progress = LessonProgress.objects.get(enrollment=enrollment, lesson=self.lesson1)
        self.assertEqual(progress.watch_time, 17)
        self.assertFalse(progress.is_completed)

    def test_lesson_watch_time_delta_allows_plausible_followup_after_elapsed_time(self):
        enrollment = Enrollment.objects.create(user=self.user, course=self.course)
        progress, _ = update_lesson_watch_progress(enrollment, self.lesson1, 120)
        LessonProgress.objects.filter(id=progress.id).update(
            updated_at=timezone.now() - timedelta(seconds=120)
        )
        response = self.client.patch(
            f'/api/enrollments/lessons/{self.lesson1.id}/watch-time/',
            {'watch_time_delta': 120},
            format='json'
        )
        self.assertEqual(response.status_code, 200)
        progress.refresh_from_db()
        self.assertEqual(progress.watch_time, 135)
        self.assertFalse(progress.is_completed)

    def test_manual_complete_requires_watch_threshold_for_video(self):
        # A trackable (YouTube) video must actually be watched to 80%.
        self.lesson1.video_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        self.lesson1.save(update_fields=['video_url'])
        enrollment = Enrollment.objects.create(user=self.user, course=self.course)
        LessonProgress.objects.create(
            enrollment=enrollment,
            user=self.user,
            lesson=self.lesson1,
            watch_time=100
        )

        response = self.client.post(f'/api/enrollments/lessons/{self.lesson1.id}/complete/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['code'], 'watch_threshold_not_met')
        progress = LessonProgress.objects.get(enrollment=enrollment, lesson=self.lesson1)
        self.assertFalse(progress.is_completed)

    def test_manual_complete_allowed_when_video_cannot_be_tracked(self):
        # No (or an unplayable) video link: the page can't measure watch time,
        # so the student must be able to mark it complete instead of being stuck.
        Enrollment.objects.create(user=self.user, course=self.course)
        response = self.client.post(f'/api/enrollments/lessons/{self.lesson1.id}/complete/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class WishlistAPITest(APITestCase):
    """Test wishlist API endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        
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
        
        self.client.force_authenticate(user=self.user)
    
    def test_add_to_wishlist(self):
        """Test adding course to wishlist."""
        url = '/api/enrollments/wishlist/add/'
        data = {'course_id': self.course.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Wishlist.objects.filter(user=self.user, course=self.course).exists())
    
    def test_add_duplicate_to_wishlist(self):
        """Test adding same course to wishlist twice."""
        Wishlist.objects.create(user=self.user, course=self.course)
        
        url = '/api/enrollments/wishlist/add/'
        data = {'course_id': self.course.id}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_list_wishlist(self):
        """Test listing wishlist items."""
        Wishlist.objects.create(user=self.user, course=self.course)
        
        url = '/api/enrollments/wishlist/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
    
    def test_remove_from_wishlist(self):
        """Test removing course from wishlist."""
        wishlist = Wishlist.objects.create(user=self.user, course=self.course)
        
        url = f'/api/enrollments/wishlist/{wishlist.id}/remove/'
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Wishlist.objects.filter(id=wishlist.id).exists())
