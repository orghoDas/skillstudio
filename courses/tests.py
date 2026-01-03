from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from .models import Course, Module, Lesson, Category, Tag, LessonResource, CourseVersion
from enrollments.models import Enrollment
from social.models import Review

User = get_user_model()


class CategoryModelTest(TestCase):
    """Tests for Category model"""

    def setUp(self):
        self.category = Category.objects.create(
            name="Programming",
            slug="programming"
        )

    def test_category_creation(self):
        """Test category is created correctly"""
        self.assertEqual(self.category.name, "Programming")
        self.assertEqual(self.category.slug, "programming")

    def test_category_str(self):
        """Test category string representation"""
        self.assertEqual(str(self.category), "Programming")


class CourseModelTest(TestCase):
    """Tests for Course model"""

    def setUp(self):
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(
            name="Programming",
            slug="programming"
        )
        self.course = Course.objects.create(
            title="Python Fundamentals",
            slug="python-fundamentals",
            description="Learn Python from scratch",
            instructor=self.instructor,
            category=self.category,
            price=Decimal('99.99'),
            level='beginner'
        )

    def test_course_creation(self):
        """Test course is created correctly"""
        self.assertEqual(self.course.title, "Python Fundamentals")
        self.assertEqual(self.course.instructor, self.instructor)
        self.assertEqual(self.course.status, 'draft')
        self.assertFalse(self.course.is_public())

    def test_course_str(self):
        """Test course string representation"""
        self.assertEqual(str(self.course), "Python Fundamentals")

    def test_course_publish(self):
        """Test publishing a course"""
        self.course.status = 'published'
        self.course.published_at = timezone.now()
        self.course.save()
        self.assertTrue(self.course.is_public())
        self.assertIsNotNone(self.course.published_at)

    def test_course_is_editable(self):
        """Test course editability"""
        self.assertTrue(self.course.is_editable())
        self.course.status = 'published'
        self.course.save()
        self.assertFalse(self.course.is_editable())

    def test_free_course_pricing(self):
        """Test free course price validation"""
        course = Course.objects.create(
            title="Free Python Course",
            slug="free-python",
            instructor=self.instructor,
            category=self.category,
            is_free=True,
            price=Decimal('99.99')
        )
        course.clean()
        self.assertEqual(course.price, 0)


class ModuleLessonModelTest(TestCase):
    """Tests for Module and Lesson models"""

    def setUp(self):
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name="Programming", slug="programming")
        self.course = Course.objects.create(
            title="Python Course",
            slug="python-course",
            instructor=self.instructor,
            category=self.category
        )
        self.module = Module.objects.create(
            course=self.course,
            title="Introduction",
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title="Getting Started",
            content_type='text',
            content_text="Welcome to the course",
            position=1,
            duration_seconds=600
        )

    def test_module_creation(self):
        """Test module is created correctly"""
        self.assertEqual(self.module.title, "Introduction")
        self.assertEqual(self.module.course, self.course)
        self.assertEqual(self.module.position, 1)

    def test_lesson_creation(self):
        """Test lesson is created correctly"""
        self.assertEqual(self.lesson.title, "Getting Started")
        self.assertEqual(self.lesson.module, self.module)
        self.assertEqual(self.lesson.duration_seconds, 600)

    def test_module_str(self):
        """Test module string representation"""
        expected = f"{self.course.title} - {self.module.title}"
        self.assertEqual(str(self.module), expected)

    def test_lesson_str(self):
        """Test lesson string representation"""
        self.assertEqual(str(self.lesson), "Getting Started")

    def test_module_ordering(self):
        """Test modules are ordered by position"""
        module2 = Module.objects.create(
            course=self.course,
            title="Advanced Topics",
            position=2
        )
        modules = list(Module.objects.filter(course=self.course))
        self.assertEqual(modules[0], self.module)
        self.assertEqual(modules[1], module2)


class CourseVersionModelTest(TestCase):
    """Tests for CourseVersion model"""

    def setUp(self):
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name="Programming", slug="programming")
        self.course = Course.objects.create(
            title="Python Course",
            slug="python-course",
            instructor=self.instructor,
            category=self.category
        )

    def test_version_creation(self):
        """Test creating a course version"""
        version = CourseVersion.objects.create(
            course=self.course,
            version_number=1,
            data={"title": "Python Course", "description": "Updated content"}
        )
        self.assertEqual(version.course, self.course)
        self.assertEqual(version.version_number, 1)

    def test_version_str(self):
        """Test version string representation"""
        version = CourseVersion.objects.create(
            course=self.course,
            version_number=1,
            data={}
        )
        self.assertEqual(str(version), f"{self.course.title} - v1")

    def test_version_ordering(self):
        """Test versions are ordered by version number descending"""
        v1 = CourseVersion.objects.create(course=self.course, version_number=1, data={})
        v2 = CourseVersion.objects.create(course=self.course, version_number=2, data={})
        versions = list(CourseVersion.objects.filter(course=self.course))
        self.assertEqual(versions[0], v2)
        self.assertEqual(versions[1], v1)


class TagModelTest(TestCase):
    """Tests for Tag model"""

    def test_tag_creation(self):
        """Test creating a tag"""
        tag = Tag.objects.create(name="Python")
        self.assertEqual(tag.name, "Python")
        self.assertEqual(str(tag), "Python")

    def test_tag_course_association(self):
        """Test associating tags with courses"""
        instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        category = Category.objects.create(name="Programming", slug="programming")
        course = Course.objects.create(
            title="Python Course",
            slug="python-course",
            instructor=instructor,
            category=category
        )
        tag = Tag.objects.create(name="Python")
        course.tags.add(tag)
        self.assertIn(tag, course.tags.all())


class EnrollmentIntegrationTest(TestCase):
    """Tests for Course and Enrollment integration"""

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
        self.category = Category.objects.create(name="Programming", slug="programming")
        self.course = Course.objects.create(
            title="Python Course",
            slug="python-course",
            instructor=self.instructor,
            category=self.category,
            status='published',
            published_at=timezone.now()
        )

    def test_enrollment_creation(self):
        """Test student can enroll in a course"""
        enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active'
        )
        self.assertEqual(enrollment.user, self.student)
        self.assertEqual(enrollment.course, self.course)
        self.assertEqual(enrollment.status, 'active')


class ReviewIntegrationTest(TestCase):
    """Tests for Course and Review integration"""

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
        self.category = Category.objects.create(name="Programming", slug="programming")
        self.course = Course.objects.create(
            title="Python Course",
            slug="python-course",
            instructor=self.instructor,
            category=self.category,
            status='published',
            published_at=timezone.now()
        )

    def test_review_creation(self):
        """Test creating a review for a course"""
        review = Review.objects.create(
            user=self.student,
            course=self.course,
            rating=5,
            title="Great Course",
            comment="Excellent content"
        )
        self.assertEqual(review.user, self.student)
        self.assertEqual(review.course, self.course)
        self.assertEqual(review.rating, 5)

    def test_multiple_reviews(self):
        """Test multiple students can review a course"""
        student2 = User.objects.create_user(
            email='student2@test.com',
            password='testpass123',
            role='student'
        )
        Review.objects.create(user=self.student, course=self.course, rating=5, comment="Great")
        Review.objects.create(user=student2, course=self.course, rating=4, comment="Good")
        
        reviews = Review.objects.filter(course=self.course)
        self.assertEqual(reviews.count(), 2)
