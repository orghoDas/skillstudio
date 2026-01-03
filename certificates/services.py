from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

# Import PDF generation function
from .pdf import generate_certificate_pdf


@transaction.atomic
def issue_certificate(user, course):
    """
    Issue a certificate for a completed course.
    
    Args:
        user: User instance
        course: Course instance
    
    Returns:
        Certificate instance
    
    Raises:
        ValidationError: If no active enrollment or enrollment not completed
    """
    from .models import Certificate
    from .pdf import generate_certificate_pdf
    from enrollments.models import Enrollment
    
    # Get enrollment
    try:
        enrollment = Enrollment.objects.get(user=user, course=course)
    except Enrollment.DoesNotExist:
        raise ValidationError(f"User is not enrolled in this course")
    
    # Validate enrollment is not canceled
    if enrollment.status == 'canceled':
        raise ValidationError("Cannot issue certificate for canceled enrollment")
    
    # Validate enrollment is completed
    if not enrollment.is_completed:
        raise ValidationError("Enrollment must be completed to issue certificate")
    
    try:
        certificate, created = Certificate.objects.get_or_create(
            user=enrollment.user,
            course=enrollment.course,
            defaults={
                'enrollment': enrollment,
                'completion_date': enrollment.completed_at or timezone.now(),
                'grade': calculate_course_grade(user, course)
            }
        )
        
        # Generate PDF if new certificate or PDF doesn't exist
        try:
            has_pdf = bool(certificate.pdf.name and certificate.pdf.name.strip())
        except (ValueError, AttributeError):
            has_pdf = False
            
        if created or not has_pdf:
            pdf_file = generate_certificate_pdf(certificate)
            certificate.pdf.save(pdf_file.name, pdf_file)
            certificate.save(update_fields=['pdf'])
        
        return certificate
    
    except IntegrityError:
        # Another process created it simultaneously
        return Certificate.objects.get(
            user=enrollment.user,
            course=enrollment.course
        )


def calculate_course_grade(user, course):
    """
    Calculate final course grade from assessments and progress.
    
    Args:
        user: User instance
        course: Course instance
    
    Returns:
        Decimal: Grade percentage (0-100)
    """
    from decimal import Decimal
    from assessments.models import QuizAttempt, Submission
    
    # Get completed quiz attempts
    quiz_attempts = QuizAttempt.objects.filter(
        user=user,
        quiz__lesson__module__course=course,
        completed_at__isnull=False
    )
    
    # Get assignment scores
    submissions = Submission.objects.filter(
        user=user,
        assignment__lesson__module__course=course,
        grade__isnull=False
    )
    
    total_score = Decimal('0.0')
    total_possible = Decimal('0.0')
    
    # Calculate quiz average
    for attempt in quiz_attempts:
        if attempt.quiz.total_marks > 0:
            total_score += attempt.score
            total_possible += attempt.quiz.total_marks
    
    # Calculate assignment average
    for submission in submissions:
        total_score += submission.grade
        total_possible += submission.assignment.max_score
    
    if total_possible > 0:
        return (total_score / total_possible) * 100
    
    return Decimal('100.0')  # Default if no assessments


def verify_certificate(verification_code):
    """
    Verify a certificate by its verification code.
    
    Args:
        verification_code: String verification code
    
    Returns:
        Certificate instance
        
    Raises:
        ValidationError: If certificate not found
    """
    from .models import Certificate
    
    try:
        return Certificate.objects.select_related(
            'user', 'course'
        ).get(verification_code=verification_code)
    except Certificate.DoesNotExist:
        raise ValidationError(f"Invalid or non-existent verification code")


def regenerate_certificate_pdf(certificate_id, user):
    """
    Regenerate PDF for an existing certificate.
    
    Args:
        certificate_id: Certificate ID
        user: User requesting regeneration (must be staff)
    
    Returns:
        Updated Certificate instance
        
    Raises:
        PermissionDenied: If user is not staff
        ValidationError: If certificate not found
    """
    from .models import Certificate
    
    # Check permission
    if not user.is_staff:
        raise PermissionDenied("Only staff can regenerate certificate PDFs")
    
    # Get certificate
    try:
        certificate = Certificate.objects.get(id=certificate_id)
    except Certificate.DoesNotExist:
        raise ValidationError(f"Certificate with ID {certificate_id} not found")
    
    # Delete old PDF if exists
    if certificate.pdf:
        certificate.pdf.delete(save=False)
    
    # Generate new PDF
    pdf_file = generate_certificate_pdf(certificate)
    certificate.pdf.save(pdf_file.name, pdf_file)
    certificate.save(update_fields=['pdf'])
    
    return certificate
