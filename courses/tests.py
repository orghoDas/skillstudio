from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from .models import Course, Module, Lesson, Category, Tag, LessonResource, CourseVersion
from enrollments.models import Enrollment, LessonProgress
from payments.models import Payment
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


class CourseDetailContentExposureTest(APITestCase):
    """Tests that public course detail responses do not expose lesson payloads."""

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
            title="Secure Python Course",
            slug="secure-python-course",
            description="Learn Python securely",
            instructor=self.instructor,
            category=self.category,
            price=Decimal('99.99'),
            is_free=False,
            status='published',
            published_at=timezone.now()
        )
        self.module = Module.objects.create(
            course=self.course,
            title="Paid Module",
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title="Paid Lesson",
            content_type='video',
            content_text="private paid lesson text",
            video_url="https://cdn.example.com/private-paid-video.mp4",
            metadata={'private_key': 'private metadata'},
            position=1,
            duration_seconds=600,
            is_free=False
        )
        LessonResource.objects.create(
            lesson=self.lesson,
            file_url="https://cdn.example.com/private-resource.pdf",
            resource_type="pdf"
        )
        self.url = reverse('course-detail', kwargs={'id': self.course.id})
        self.sensitive_markers = [
            'private paid lesson text',
            'https://cdn.example.com/private-paid-video.mp4',
            'private metadata',
            'https://cdn.example.com/private-resource.pdf',
        ]
        self.forbidden_lesson_keys = {
            'content_text',
            'video_url',
            'metadata',
            'resources',
            'file_url',
        }

    def assert_no_sensitive_lesson_payload(self, payload):
        payload_text = repr(payload)
        for marker in self.sensitive_markers:
            self.assertNotIn(marker, payload_text)

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    self.assertNotIn(key, self.forbidden_lesson_keys)
                    walk(child)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(payload)

    def test_anonymous_course_detail_does_not_expose_paid_lesson_payload(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lesson_data = response.data['modules'][0]['lessons'][0]

        self.assertEqual(lesson_data['title'], self.lesson.title)
        self.assertTrue(lesson_data['is_locked'])
        self.assertNotIn('content_text', lesson_data)
        self.assertNotIn('video_url', lesson_data)
        self.assertNotIn('metadata', lesson_data)
        self.assertNotIn('resources', lesson_data)
        self.assert_no_sensitive_lesson_payload(response.data)

    def test_enrolled_course_detail_still_uses_catalog_lesson_shape(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active'
        )
        self.client.force_authenticate(user=self.student)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lesson_data = response.data['modules'][0]['lessons'][0]

        self.assertTrue(response.data['is_enrolled'])
        self.assertFalse(lesson_data['is_locked'])
        self.assertNotIn('content_text', lesson_data)
        self.assertNotIn('video_url', lesson_data)
        self.assertNotIn('metadata', lesson_data)
        self.assertNotIn('resources', lesson_data)
        self.assert_no_sensitive_lesson_payload(response.data)

    def test_anonymous_curriculum_aliases_do_not_expose_paid_lesson_payload(self):
        urls = [
            reverse('module-list', kwargs={'course_id': self.course.id}),
            reverse('course-sections', kwargs={'course_id': self.course.id}),
            reverse('course-sections-slug', kwargs={'slug': self.course.slug}),
            reverse('section-lessons', kwargs={'id': self.module.id}),
            reverse('lesson-list', kwargs={'module_id': self.module.id}),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assert_no_sensitive_lesson_payload(response.data)

    def test_unenrolled_student_curriculum_aliases_do_not_expose_paid_lesson_payload(self):
        self.client.force_authenticate(user=self.student)
        urls = [
            reverse('module-list', kwargs={'course_id': self.course.id}),
            reverse('course-sections', kwargs={'course_id': self.course.id}),
            reverse('section-lessons', kwargs={'id': self.module.id}),
            reverse('lesson-list', kwargs={'module_id': self.module.id}),
        ]

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assert_no_sensitive_lesson_payload(response.data)

    def test_enrolled_student_curriculum_aliases_still_use_catalog_lesson_shape(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active'
        )
        self.client.force_authenticate(user=self.student)

        response = self.client.get(reverse('section-lessons', kwargs={'id': self.module.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        lesson_data = response.data['results'][0]
        self.assertEqual(lesson_data['title'], self.lesson.title)
        self.assertFalse(lesson_data['is_locked'])
        self.assert_no_sensitive_lesson_payload(response.data)

    def test_unpublished_course_curriculum_aliases_are_restricted_to_owner(self):
        self.course.status = 'draft'
        self.course.published_at = None
        self.course.save(update_fields=['status', 'published_at'])

        public_urls = [
            reverse('module-list', kwargs={'course_id': self.course.id}),
            reverse('course-sections', kwargs={'course_id': self.course.id}),
            reverse('course-sections-slug', kwargs={'slug': self.course.slug}),
            reverse('section-lessons', kwargs={'id': self.module.id}),
        ]

        for url in public_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse('module-list', kwargs={'course_id': self.course.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assert_no_sensitive_lesson_payload(response.data)


class CourseModerationWorkflowAPITest(APITestCase):
    """Tests that generic authoring endpoints cannot bypass moderation."""

    def setUp(self):
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.category = Category.objects.create(name="Programming", slug="programming")
        self.client.force_authenticate(user=self.instructor)

    def test_course_create_payload_cannot_set_published_status(self):
        response = self.client.post(
            '/api/courses/create/',
            {
                'title': 'Bypass Course',
                'description': 'Trying to publish directly',
                'price': '10.00',
                'is_free': False,
                'level': 'beginner',
                'category': self.category.id,
                'status': 'published',
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        course = Course.objects.get(id=response.data['id'])
        self.assertEqual(course.status, 'draft')

    def test_course_update_payload_cannot_publish_course(self):
        course = Course.objects.create(
            title='Draft Course',
            instructor=self.instructor,
            category=self.category,
            status='draft'
        )

        response = self.client.patch(
            f'/api/courses/{course.id}/update/',
            {'status': 'published'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course.refresh_from_db()
        self.assertEqual(course.status, 'draft')

    def test_instructor_cannot_use_publish_endpoint(self):
        course = Course.objects.create(
            title='Course Under Review',
            instructor=self.instructor,
            category=self.category,
            status='under_review',
            submitted_for_review_at=timezone.now()
        )

        response = self.client.post(f'/api/courses/{course.id}/publish/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        course.refresh_from_db()
        self.assertEqual(course.status, 'under_review')

    def test_published_course_cannot_receive_new_lessons(self):
        course = Course.objects.create(
            title='Published Course',
            instructor=self.instructor,
            category=self.category,
            status='published',
            published_at=timezone.now()
        )
        module = Module.objects.create(course=course, title='Published Module', position=1)

        response = self.client.post(
            f'/api/courses/sections/{module.id}/lessons/',
            {
                'title': 'Late Lesson',
                'content_type': 'text',
                'content_text': 'Should not be added directly',
                'position': 1,
            },
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Lesson.objects.filter(module=module, title='Late Lesson').exists())


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


class CourseRoutedAPIDriftTest(APITestCase):
    """Regression tests for routed course endpoints that drifted from models/services."""

    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            email='student@test.com',
            password='testpass123',
            role='student'
        )
        self.instructor = User.objects.create_user(
            email='instructor@test.com',
            password='testpass123',
            role='instructor'
        )
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            role='admin'
        )
        self.category = Category.objects.create(name="Programming", slug="programming")
        self.course = Course.objects.create(
            title="Python Course",
            slug="python-course-routed",
            instructor=self.instructor,
            category=self.category,
            status='published',
            published_at=timezone.now(),
            price=Decimal('49.00'),
            is_free=False,
        )
        self.module = Module.objects.create(course=self.course, title="Module", position=1)
        self.lesson = Lesson.objects.create(
            module=self.module,
            title="Next Lesson",
            content_type='text',
            content_text='Private content',
            position=1,
            is_free=False,
        )

    def test_resume_learning_returns_next_lesson_for_active_enrollment(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active',
        )
        self.client.force_authenticate(user=self.student)

        response = self.client.get(reverse('resume-learning', kwargs={'course_id': self.course.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['lesson_id'], self.lesson.id)
        self.assertEqual(response.data['lesson_title'], self.lesson.title)
        self.assertEqual(response.data['module_title'], self.module.title)

    def test_resume_learning_reports_completed_when_required_lessons_done(self):
        enrollment = Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active',
        )
        LessonProgress.objects.create(
            enrollment=enrollment,
            user=self.student,
            lesson=self.lesson,
            is_completed=True,
        )
        self.client.force_authenticate(user=self.student)

        response = self.client.get(reverse('resume-learning', kwargs={'course_id': self.course.id}))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['completed'])

    def test_admin_course_stats_uses_completed_course_payments_for_revenue(self):
        Enrollment.objects.create(
            user=self.student,
            course=self.course,
            status='active',
        )
        Payment.objects.create(
            user=self.student,
            instructor=self.instructor,
            course=self.course,
            amount=Decimal('49.00'),
            original_amount=Decimal('49.00'),
            status='completed',
        )
        self.client.force_authenticate(user=self.admin)

        response = self.client.get(reverse('admin-course-stats'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_revenue'], 49.0)
        self.assertEqual(response.data['courses']['published'], 1)
        self.assertEqual(response.data['enrollments']['active'], 1)


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
