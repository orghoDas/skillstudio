from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from rest_framework.test import APIClient

from courses.models import Course, Module, Lesson
from enrollments.models import Enrollment, LessonProgress
from certificates.models import Certificate
from .models import LearningActivity, StudentProfile, StudentNote, StudentBookmark, Wallet, WalletTransaction
from .services import (
    get_or_create_student_profile,
    update_student_profile,
    create_student_note,
    update_student_note,
    delete_student_note,
    create_bookmark,
    delete_bookmark,
    get_student_notes,
    get_student_bookmarks,
    get_student_activity_feed,
    get_student_dashboard_data,
    get_learning_streak,
    get_weekly_learning_progress,
    get_student_achievements,
)

User = get_user_model()


class WalletLedgerTests(TestCase):
    """Canonical wallet: every balance change writes an atomic ledger row."""

    def setUp(self):
        self.user = User.objects.create_user(email='wallet@example.com', password='pw')
        self.wallet = Wallet.objects.create(user=self.user, balance=Decimal('0.00'))

    def test_add_money_credits_and_writes_ledger_row(self):
        txn = self.wallet.add_money(Decimal('50.00'), description='top up')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('50.00'))
        self.assertIsInstance(txn, WalletTransaction)
        self.assertEqual(txn.transaction_type, 'credit')
        self.assertEqual(txn.amount, Decimal('50.00'))
        self.assertEqual(txn.balance_after, Decimal('50.00'))
        self.assertEqual(self.wallet.transactions.count(), 1)

    def test_deduct_money_debits_and_writes_ledger_row(self):
        self.wallet.add_money(Decimal('50.00'))
        txn = self.wallet.deduct_money(Decimal('20.00'), description='buy')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('30.00'))
        self.assertEqual(txn.transaction_type, 'debit')
        self.assertEqual(txn.balance_after, Decimal('30.00'))
        self.assertEqual(self.wallet.transactions.count(), 2)

    def test_deduct_more_than_balance_raises_and_writes_nothing(self):
        self.wallet.add_money(Decimal('10.00'))
        with self.assertRaises(ValueError):
            self.wallet.deduct_money(Decimal('25.00'))
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('10.00'))
        # Only the credit row exists; the failed debit wrote no ledger row.
        self.assertEqual(self.wallet.transactions.filter(transaction_type='debit').count(), 0)

    def test_non_positive_amount_raises(self):
        with self.assertRaises(ValueError):
            self.wallet.add_money(Decimal('0'))
        with self.assertRaises(ValueError):
            self.wallet.deduct_money(Decimal('-5'))


class StudentProfileModelTests(TestCase):
    """Test StudentProfile model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
    
    def test_profile_creation(self):
        """Test creating a student profile."""
        profile = StudentProfile.objects.create(
            user=self.user,
            preferred_learning_style='visual',
            weekly_study_hours=10
        )
        
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.preferred_learning_style, 'visual')
        self.assertEqual(profile.weekly_study_hours, 10)
    
    def test_statistics_follow_new_enrollments(self):
        profile = StudentProfile.objects.create(user=self.user)
        self.assertEqual(profile.total_courses_enrolled, 0)
        
        # Create some data
        course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        Enrollment.objects.create(user=self.user, course=course, status='active')
        
        self.assertEqual(profile.total_courses_enrolled, 1)


class StudentNoteModelTests(TestCase):
    """Test StudentNote model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1',
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            position=1
        , content_type='text', content_text='Sample content')
    
    def test_note_creation(self):
        """Test creating a student note."""
        note = StudentNote.objects.create(
            user=self.user,
            lesson=self.lesson,
            content='This is a test note',
            timestamp=120
        )
        
        self.assertEqual(note.user, self.user)
        self.assertEqual(note.lesson, self.lesson)
        self.assertEqual(note.content, 'This is a test note')
        self.assertEqual(note.timestamp, 120)
        self.assertFalse(note.is_pinned)


class StudentBookmarkModelTests(TestCase):
    """Test StudentBookmark model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1',
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            position=1
        , content_type='text', content_text='Sample content')
    
    def test_course_bookmark(self):
        """Test bookmarking a course."""
        bookmark = StudentBookmark.objects.create(
            user=self.user,
            course=self.course,
            note='Interesting course'
        )
        
        self.assertEqual(bookmark.user, self.user)
        self.assertEqual(bookmark.course, self.course)
        self.assertIsNone(bookmark.lesson)
    
    def test_lesson_bookmark(self):
        """Test bookmarking a lesson."""
        bookmark = StudentBookmark.objects.create(
            user=self.user,
            lesson=self.lesson,
            note='Important lesson'
        )
        
        self.assertEqual(bookmark.user, self.user)
        self.assertEqual(bookmark.lesson, self.lesson)
        self.assertIsNone(bookmark.course)


class StudentProfileServiceTests(TestCase):
    """Test student profile services."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
    
    def test_get_or_create_profile(self):
        """Test getting or creating profile."""
        profile = get_or_create_student_profile(self.user)
        
        self.assertIsNotNone(profile)
        self.assertEqual(profile.user, self.user)
        
        # Should return same profile on second call
        profile2 = get_or_create_student_profile(self.user)
        self.assertEqual(profile.id, profile2.id)
    
    def test_update_profile(self):
        """Test updating profile."""
        profile = get_or_create_student_profile(self.user)
        
        updated = update_student_profile(
            self.user,
            preferred_learning_style='auditory',
            weekly_study_hours=15
        )
        
        self.assertEqual(updated.preferred_learning_style, 'auditory')
        self.assertEqual(updated.weekly_study_hours, 15)
    
    def test_update_nonexistent_profile(self):
        """Test updating profile that doesn't exist."""
        with self.assertRaises(ValidationError):
            update_student_profile(self.user, weekly_study_hours=10)


class StudentNoteServiceTests(TestCase):
    """Test student note services."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1',
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            position=1
        , content_type='text', content_text='Sample content')
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status='active'
        )
    
    def test_create_note_success(self):
        """Test creating note successfully."""
        note = create_student_note(
            self.user,
            self.lesson.id,
            'Test note',
            timestamp=60,
            tags=['important']
        )
        
        self.assertIsNotNone(note)
        self.assertEqual(note.content, 'Test note')
        self.assertEqual(note.timestamp, 60)
        self.assertEqual(note.tags, ['important'])
    
    def test_create_note_not_enrolled(self):
        """Test creating note without enrollment."""
        with self.assertRaises(ValidationError):
            create_student_note(
                self.other_user,
                self.lesson.id,
                'Test note'
            )
    
    def test_create_note_invalid_lesson(self):
        """Test creating note for invalid lesson."""
        with self.assertRaises(ValidationError):
            create_student_note(
                self.user,
                99999,
                'Test note'
            )
    
    def test_update_note(self):
        """Test updating a note."""
        note = create_student_note(self.user, self.lesson.id, 'Original')
        
        updated = update_student_note(
            note.id,
            self.user,
            content='Updated',
            is_pinned=True
        )
        
        self.assertEqual(updated.content, 'Updated')
        self.assertTrue(updated.is_pinned)
    
    def test_update_note_wrong_user(self):
        """Test updating note by wrong user."""
        note = create_student_note(self.user, self.lesson.id, 'Original')
        
        with self.assertRaises(PermissionDenied):
            update_student_note(note.id, self.other_user, content='Hacked')
    
    def test_delete_note(self):
        """Test deleting a note."""
        note = create_student_note(self.user, self.lesson.id, 'To delete')
        note_id = note.id
        
        delete_student_note(note_id, self.user)
        
        self.assertFalse(StudentNote.objects.filter(id=note_id).exists())
    
    def test_delete_note_wrong_user(self):
        """Test deleting note by wrong user."""
        note = create_student_note(self.user, self.lesson.id, 'Protected')
        
        with self.assertRaises(PermissionDenied):
            delete_student_note(note.id, self.other_user)
    
    def test_get_notes_filtered(self):
        """Test getting notes with filters."""
        note1 = create_student_note(self.user, self.lesson.id, 'Note 1')
        note2 = create_student_note(self.user, self.lesson.id, 'Note 2')
        
        notes = get_student_notes(self.user, lesson_id=self.lesson.id)
        
        self.assertEqual(notes.count(), 2)


class StudentBookmarkServiceTests(TestCase):
    """Test student bookmark services."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1',
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            position=1
        , content_type='text', content_text='Sample content')
    
    def test_create_course_bookmark(self):
        """Test creating course bookmark."""
        bookmark = create_bookmark(
            self.user,
            course_id=self.course.id,
            note='Good course'
        )
        
        self.assertIsNotNone(bookmark)
        self.assertEqual(bookmark.course, self.course)
        self.assertIsNone(bookmark.lesson)
    
    def test_create_lesson_bookmark(self):
        """Test creating lesson bookmark."""
        bookmark = create_bookmark(
            self.user,
            lesson_id=self.lesson.id,
            note='Good lesson'
        )
        
        self.assertIsNotNone(bookmark)
        self.assertEqual(bookmark.lesson, self.lesson)
        self.assertIsNone(bookmark.course)
    
    def test_create_bookmark_no_target(self):
        """Test creating bookmark without target."""
        with self.assertRaises(ValidationError):
            create_bookmark(self.user)
    
    def test_create_bookmark_both_targets(self):
        """Test creating bookmark with both targets."""
        with self.assertRaises(ValidationError):
            create_bookmark(
                self.user,
                course_id=self.course.id,
                lesson_id=self.lesson.id
            )
    
    def test_delete_bookmark(self):
        """Test deleting bookmark."""
        bookmark = create_bookmark(self.user, course_id=self.course.id)
        bookmark_id = bookmark.id
        
        delete_bookmark(bookmark_id, self.user)
        
        self.assertFalse(StudentBookmark.objects.filter(id=bookmark_id).exists())
    
    def test_delete_bookmark_wrong_user(self):
        """Test deleting bookmark by wrong user."""
        bookmark = create_bookmark(self.user, course_id=self.course.id)
        
        with self.assertRaises(PermissionDenied):
            delete_bookmark(bookmark.id, self.other_user)
    
    def test_get_bookmarks(self):
        """Test getting bookmarks."""
        bookmark1 = create_bookmark(self.user, course_id=self.course.id)
        bookmark2 = create_bookmark(self.user, lesson_id=self.lesson.id)
        
        bookmarks = get_student_bookmarks(self.user)
        
        self.assertEqual(bookmarks.count(), 2)

    def test_private_course_and_lesson_look_missing_when_bookmarked(self):
        client = APIClient()
        client.force_authenticate(self.other_user)
        url = '/api/students/bookmarks/'
        for course_status in ('draft', 'under_review', 'archived'):
            self.course.status = course_status
            self.course.save(update_fields=['status'])
            for field, target in (('course', self.course), ('lesson', self.lesson)):
                with self.subTest(course_status=course_status, field=field):
                    hidden = client.post(url, {field: target.pk}, format='json')
                    missing = client.post(url, {field: 999999}, format='json')
                    self.assertEqual(hidden.status_code, 400)
                    self.assertEqual(hidden.json(), missing.json())
        self.assertFalse(StudentBookmark.objects.filter(user=self.other_user).exists())

    def test_archived_bookmarks_are_hidden_when_access_ends_and_remain_deletable(self):
        self.course.status = 'archived'
        self.course.save(update_fields=['status'])
        enrollment = Enrollment.objects.create(user=self.other_user, course=self.course, status='completed')
        client = APIClient()
        client.force_authenticate(self.other_user)
        url = '/api/students/bookmarks/'
        bookmarks = []
        for field, target in (('course', self.course), ('lesson', self.lesson)):
            response = client.post(url, {field: target.pk}, format='json')
            self.assertEqual(response.status_code, 201, response.data)
            bookmarks.append(response.data['id'])
        self.assertEqual(client.get(url).data['count'], 2)

        enrollment.status = 'canceled'
        enrollment.save(update_fields=['status'])
        self.assertEqual(client.get(url).data['count'], 0)
        for bookmark_id in bookmarks:
            detail = f'{url}{bookmark_id}/'
            self.assertEqual(client.get(detail).status_code, 404)
            self.assertEqual(client.patch(detail, {'note': 'update'}, format='json').status_code, 404)
            self.assertEqual(client.delete(detail).status_code, 204)

    def test_can_edit_note_but_cannot_retarget_to_private_content(self):
        published = Course.objects.create(title='Public course', instructor=self.user, status='published')
        client = APIClient()
        client.force_authenticate(self.other_user)
        bookmark = create_bookmark(self.other_user, course_id=published.pk)
        url = f'/api/students/bookmarks/{bookmark.pk}/'
        for data, field in (
            ({'course': self.course.pk}, 'course'),
            ({'course': None, 'lesson': self.lesson.pk}, 'lesson'),
        ):
            for method in (client.patch, client.put):
                with self.subTest(field=field, method=method.__name__):
                    response = method(url, data, format='json')
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(field, response.data['fields'])
        response = client.patch(url, {'note': 'New note'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['note'], 'New note')
        bookmark.refresh_from_db()
        self.assertEqual(bookmark.course_id, published.pk)

    def test_admin_can_bookmark_and_read_private_course(self):
        admin = User.objects.create_user(email='bookmark-admin@example.test', role='admin')
        client = APIClient()
        client.force_authenticate(admin)
        url = '/api/students/bookmarks/'
        response = client.post(url, {'course': self.course.pk}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        detail = client.get(f"{url}{response.data['id']}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['course_title'], self.course.title)


class StudentDashboardServiceTests(TestCase):
    """Test student dashboard services."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1',
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            position=1
        , content_type='text', content_text='Sample content')
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status='active'
        )
    
    def test_get_activity_feed(self):
        """Test getting activity feed."""
        feed = get_student_activity_feed(self.user, limit=10)
        
        self.assertIsInstance(feed, list)
    
    def test_get_dashboard_data(self):
        """Test getting dashboard data."""
        dashboard = get_student_dashboard_data(self.user)
        
        self.assertIsInstance(dashboard, list)
        self.assertGreater(len(dashboard), 0)
    
    def test_get_learning_streak(self):
        """Test getting learning streak."""
        streak = get_learning_streak(self.user)
        
        self.assertIn('current_streak', streak)
        self.assertIn('longest_streak', streak)
    
    def test_get_weekly_progress(self):
        """Test getting weekly progress."""
        progress = get_weekly_learning_progress(self.user)
        
        self.assertIn('active_days', progress)
        self.assertIn('total_watch_time', progress)

    def test_completion_percentage_and_certificate_use_their_own_records(self):
        free = Lesson.objects.create(module=self.module, title='Preview', position=2, is_free=True)
        now = timezone.now()
        for lesson in (self.lesson, free):
            LessonProgress.objects.create(
                enrollment=self.enrollment, user=self.user, lesson=lesson, is_completed=True,
                completed_at=now, watch_time=30,
            )
        self.enrollment.status = 'completed'
        self.enrollment.is_completed = True
        self.enrollment.completed_at = now
        self.enrollment.save(update_fields=['status', 'is_completed', 'completed_at'])

        client = APIClient()
        client.force_authenticate(self.user)
        data = client.get('/api/students/dashboard/').data
        course = data['courses'][0]
        self.assertEqual((course['completed_lessons'], course['total_lessons'], course['progress_percentage']), (1, 1, 100))
        self.assertFalse(course['has_certificate'])
        self.assertEqual(course['primary_action'], 'view_course')
        self.assertEqual(data['summary'], {
            'total_courses_enrolled': 1, 'total_courses_completed': 1, 'total_certificates_earned': 0,
        })
        profile = client.get('/api/accounts/profile/').data['student_profile']
        self.assertEqual(profile['total_courses_completed'], 1)
        self.assertEqual(profile['total_watch_time'], 60)

        # A legacy certificate may predate the optional enrollment link.
        Certificate.objects.create(user=self.user, course=self.course)
        data = client.get('/api/students/dashboard/').data
        self.assertTrue(data['courses'][0]['has_certificate'])
        self.assertEqual(data['courses'][0]['primary_action'], 'view_certificate')
        self.assertEqual(data['summary']['total_certificates_earned'], 1)
        self.assertEqual(client.get('/api/students/profile/').data['total_certificates_earned'], 1)

    def test_watch_activity_keeps_each_local_day_and_yesterday_keeps_the_streak(self):
        client = APIClient()
        client.force_authenticate(self.user)
        self.lesson.duration_seconds = 100
        self.lesson.save(update_fields=['duration_seconds'])
        first = datetime(2026, 11, 8, 18, 10, tzinfo=UTC)
        watch = f'/api/enrollments/lessons/{self.lesson.pk}/watch-time/?timezone=Asia%2FDhaka'
        for when, delta in ((first, 6), (first + timedelta(seconds=4), 4), (first + timedelta(days=1), 5)):
            with patch('django.utils.timezone.now', return_value=when):
                self.assertEqual(client.patch(watch, {'watch_time_delta': delta}, format='json').status_code, 200)
        with patch('django.utils.timezone.now', return_value=first + timedelta(days=2)):
            self.assertEqual(client.patch(watch, {'watch_time_delta': 0}, format='json').status_code, 200)
            self.assertEqual(client.patch(watch, {'watch_time_delta': 500}, format='json').status_code, 400)
            data = client.get('/api/students/dashboard/?timezone=Asia%2FDhaka').data
        self.assertEqual(data['streak'], {'current_streak': 2, 'longest_streak': 2})
        self.assertEqual(data['weekly_progress'], {'active_days': 2, 'total_watch_time': 15})
        self.assertEqual(
            list(LearningActivity.objects.filter(user=self.user).order_by('date').values_list('date', 'watch_seconds')),
            [(date(2026, 11, 9), 10), (date(2026, 11, 10), 5)],
        )

    def test_text_completion_records_activity_without_replayed_completion_counting_again(self):
        client = APIClient()
        client.force_authenticate(self.user)
        first = datetime(2026, 11, 8, 18, 10, tzinfo=UTC)
        complete = f'/api/enrollments/lessons/{self.lesson.pk}/complete/?timezone=Asia%2FDhaka'
        for when in (first, first + timedelta(days=1)):
            with patch('django.utils.timezone.now', return_value=when):
                self.assertEqual(client.post(complete).status_code, 200)
        self.assertEqual(list(LearningActivity.objects.filter(user=self.user).values_list('date', flat=True)), [
            date(2026, 11, 9),
        ])
    
    def test_get_achievements(self):
        """Test getting achievements."""
        streak_data = {'current_streak': 5, 'longest_streak': 10}
        achievements = get_student_achievements(self.user, streak_data)
        
        self.assertIsInstance(achievements, list)
