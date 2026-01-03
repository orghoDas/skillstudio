from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from decimal import Decimal
from unittest.mock import patch

from courses.models import Course, Module, Lesson
from enrollments.models import Enrollment, LessonProgress
from certificates.models import Certificate
from .models import StudentProfile, StudentNote, StudentBookmark
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
    
    def test_update_statistics(self):
        """Test updating profile statistics."""
        profile = StudentProfile.objects.create(user=self.user)
        
        # Create some data
        course = Course.objects.create(
            title='Test Course',
            instructor=self.user,
            price=Decimal('99.99')
        )
        Enrollment.objects.create(user=self.user, course=course, status='active')
        
        profile.update_statistics()
        
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
    
    def test_get_achievements(self):
        """Test getting achievements."""
        streak_data = {'current_streak': 5, 'longest_streak': 10}
        achievements = get_student_achievements(self.user, streak_data)
        
        self.assertIsInstance(achievements, list)
