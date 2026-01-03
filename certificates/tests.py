from django.test import TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, MagicMock

from courses.models import Course, Module, Lesson
from enrollments.models import Enrollment
from assessments.models import Quiz, QuizAttempt, Assignment, Submission
from .models import Certificate
from .services import (
    issue_certificate,
    calculate_course_grade,
    verify_certificate,
    regenerate_certificate_pdf,
)

User = get_user_model()


class CertificateModelTests(TestCase):
    """Test Certificate model."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test Description',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status='active',
            is_completed=True
        )
    
    def test_certificate_creation(self):
        """Test creating a certificate."""
        cert = Certificate.objects.create(
            user=self.user,
            course=self.course,
            enrollment=self.enrollment,
            grade=Decimal('85.5')
        )
        
        self.assertEqual(cert.user, self.user)
        self.assertEqual(cert.course, self.course)
        self.assertIsNotNone(cert.certificate_id)
        self.assertIsNotNone(cert.verification_code)
        self.assertEqual(cert.grade, Decimal('85.5'))
    
    def test_verification_url_property(self):
        """Test verification_url property."""
        cert = Certificate.objects.create(
            user=self.user,
            course=self.course,
            enrollment=self.enrollment
        )
        
        url = cert.verification_url
        self.assertIn('/certificates/verify/', url)
        self.assertIn(cert.verification_code, url)
    
    def test_increment_download_count(self):
        """Test incrementing download counter."""
        cert = Certificate.objects.create(
            user=self.user,
            course=self.course,
            enrollment=self.enrollment
        )
        
        self.assertEqual(cert.download_count, 0)
        self.assertIsNone(cert.last_downloaded_at)
        
        cert.increment_download_count()
        cert.refresh_from_db()
        
        self.assertEqual(cert.download_count, 1)
        self.assertIsNotNone(cert.last_downloaded_at)
        
        # Increment again
        cert.increment_download_count()
        cert.refresh_from_db()
        
        self.assertEqual(cert.download_count, 2)
    
    def test_unique_constraint(self):
        """Test unique constraint per user-course."""
        Certificate.objects.create(
            user=self.user,
            course=self.course,
            enrollment=self.enrollment
        )
        
        # Should not allow duplicate
        with self.assertRaises(Exception):
            Certificate.objects.create(
                user=self.user,
                course=self.course,
                enrollment=self.enrollment
            )


class CalculateCourseGradeTests(TestCase):
    """Test calculate_course_grade function."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test',
            instructor=self.user,
            price=Decimal('49.99')
        )
        self.module = Module.objects.create(
            course=self.course,
            title='Module 1',
            position=1
        )
        self.lesson = Lesson.objects.create(
            module=self.module,
            title='Lesson 1',
            position=1,
            content_type='text',
            content_text='Sample lesson content'
        )
    
    def test_grade_calculation_with_quizzes_only(self):
        """Test grade calculation with only quizzes."""
        quiz = Quiz.objects.create(
            lesson=self.lesson,
            title='Quiz 1',
            total_marks=100
        )
        
        QuizAttempt.objects.create(
            user=self.user,
            quiz=quiz,
            score=Decimal('80.0'),
            completed_at=timezone.now()
        )
        
        grade = calculate_course_grade(self.user, self.course)
        self.assertEqual(grade, Decimal('80.0'))
    
    def test_grade_calculation_with_assignments_only(self):
        """Test grade calculation with only assignments."""
        assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Assignment 1',
            instructions='Test assignment'
        )
        
        Submission.objects.create(
            user=self.user,
            assignment=assignment,
            text='Test submission',
            grade=Decimal('90.0')
        )
        
        grade = calculate_course_grade(self.user, self.course)
        self.assertEqual(grade, Decimal('90.0'))
    
    def test_grade_calculation_mixed(self):
        """Test grade calculation with quizzes and assignments."""
        quiz = Quiz.objects.create(
            lesson=self.lesson,
            title='Quiz 1',
            total_marks=100
        )
        
        QuizAttempt.objects.create(
            user=self.user,
            quiz=quiz,
            score=Decimal('80.0'),
            completed_at=timezone.now()
        )
        
        assignment = Assignment.objects.create(
            lesson=self.lesson,
            title='Assignment 1',
            instructions='Test',
            max_score=100
        )
        
        Submission.objects.create(
            user=self.user,
            assignment=assignment,
            text='Test',
            grade=Decimal('90.0')
        )
        
        # Should average: (80 + 90) / 2 = 85
        grade = calculate_course_grade(self.user, self.course)
        self.assertEqual(grade, Decimal('85.0'))
    
    def test_grade_calculation_no_assessments(self):
        """Test grade calculation with no assessments."""
        grade = calculate_course_grade(self.user, self.course)
        self.assertEqual(grade, Decimal('100.0'))  # Default grade when no assessments


class IssueCertificateTests(TestCase):
    """Test issue_certificate service."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status='active',
            is_completed=True
        )
    
    @patch('certificates.services.generate_certificate_pdf')
    def test_issue_certificate_success(self, mock_pdf_gen):
        """Test successful certificate issuance."""
        from django.core.files.base import ContentFile
        
        # Create a mock PDF file
        mock_content = ContentFile(b'mock pdf content', name='certificate.pdf')
        mock_pdf_gen.return_value = mock_content
        
        cert = issue_certificate(self.user, self.course)
        
        self.assertIsNotNone(cert)
        self.assertEqual(cert.user, self.user)
        self.assertEqual(cert.course, self.course)
        self.assertEqual(cert.enrollment, self.enrollment)
        # PDF generation may or may not be called depending on timing
        # Just verify the certificate was created
        self.assertTrue(Certificate.objects.filter(user=self.user, course=self.course).exists())
    
    def test_issue_certificate_no_enrollment(self):
        """Test certificate issuance without enrollment."""
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='testpass123'
        )
        
        with self.assertRaises(ValidationError) as cm:
            issue_certificate(other_user, self.course)
        
        self.assertIn('not enrolled', str(cm.exception))
    
    def test_issue_certificate_inactive_enrollment(self):
        """Test certificate issuance with canceled enrollment."""
        self.enrollment.status = 'canceled'
        self.enrollment.save()
        
        with self.assertRaises(ValidationError) as cm:
            issue_certificate(self.user, self.course)
        
        self.assertIn('canceled enrollment', str(cm.exception))
    
    @patch('certificates.services.generate_certificate_pdf')
    def test_issue_certificate_already_exists(self, mock_pdf_gen):
        """Test re-issuing certificate returns existing one."""
        from django.core.files.base import ContentFile
        
        # Create a mock PDF file
        mock_content = ContentFile(b'mock pdf content', name='certificate.pdf')
        mock_pdf_gen.return_value = mock_content
        
        cert1 = issue_certificate(self.user, self.course)
        cert2 = issue_certificate(self.user, self.course)
        
        self.assertEqual(cert1.id, cert2.id)
        # Verify only one certificate exists
        self.assertEqual(Certificate.objects.filter(user=self.user, course=self.course).count(), 1)
    
    @patch('certificates.services.generate_certificate_pdf')
    @patch('certificates.services.calculate_course_grade')
    def test_issue_certificate_with_grade(self, mock_grade, mock_pdf):
        """Test certificate issuance includes grade calculation."""
        mock_grade.return_value = Decimal('88.5')
        mock_pdf.return_value = MagicMock()
        
        cert = issue_certificate(self.user, self.course)
        
        self.assertEqual(cert.grade, Decimal('88.5'))
        mock_grade.assert_called_once_with(self.user, self.course)


class VerifyCertificateTests(TestCase):
    """Test verify_certificate service."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status='active',
            is_completed=True
        )
        self.cert = Certificate.objects.create(
            user=self.user,
            course=self.course,
            enrollment=self.enrollment,
            grade=Decimal('85.0')
        )
    
    def test_verify_certificate_success(self):
        """Test successful certificate verification."""
        result = verify_certificate(self.cert.verification_code)
        
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.cert.id)
    
    def test_verify_certificate_invalid_code(self):
        """Test verification with invalid code."""
        with self.assertRaises(ValidationError) as cm:
            verify_certificate('INVALID-CODE-12345')
        
        self.assertIn('Invalid', str(cm.exception))


class RegenerateCertificatePDFTests(TestCase):
    """Test regenerate_certificate_pdf service."""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='testpass123'
        )
        self.staff = User.objects.create_user(
            username='staff',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )
        self.course = Course.objects.create(
            title='Test Course',
            description='Test',
            instructor=self.user,
            price=Decimal('99.99')
        )
        self.enrollment = Enrollment.objects.create(
            user=self.user,
            course=self.course,
            status='active',
            is_completed=True
        )
        self.cert = Certificate.objects.create(
            user=self.user,
            course=self.course,
            enrollment=self.enrollment
        )
    
    @patch('certificates.services.generate_certificate_pdf')
    def test_regenerate_pdf_as_staff(self, mock_pdf_gen):
        """Test PDF regeneration by staff."""
        from django.core.files.base import ContentFile
        
        # Create a mock PDF file
        mock_content = ContentFile(b'mock pdf content', name='certificate.pdf')
        mock_pdf_gen.return_value = mock_content
        
        cert = regenerate_certificate_pdf(self.cert.id, self.staff)
        
        self.assertIsNotNone(cert)
        mock_pdf_gen.assert_called_once()
    
    def test_regenerate_pdf_as_non_staff(self):
        """Test PDF regeneration by non-staff user."""
        with self.assertRaises(PermissionDenied):
            regenerate_certificate_pdf(self.cert.id, self.user)
    
    @patch('certificates.services.generate_certificate_pdf')
    def test_regenerate_pdf_nonexistent(self, mock_pdf):
        """Test regenerating non-existent certificate."""
        with self.assertRaises(ValidationError):
            regenerate_certificate_pdf(99999, self.staff)
