import logging

from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

# Import PDF generation function
from .pdf import generate_certificate_pdf

logger = logging.getLogger(__name__)


@transaction.atomic
def issue_certificate(user, course, schedule_pdf=True):
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
        
        if schedule_pdf:
            schedule_certificate_pdf_render(certificate.id, force=False)
        
        return certificate
    
    except IntegrityError:
        # Another process created it simultaneously
        certificate = Certificate.objects.get(
            user=enrollment.user,
            course=enrollment.course
        )
        if schedule_pdf:
            schedule_certificate_pdf_render(certificate.id, force=False)
        return certificate


def certificate_has_pdf(certificate):
    try:
        return bool(certificate.pdf.name and certificate.pdf.name.strip())
    except (ValueError, AttributeError):
        return False


def schedule_certificate_pdf_render(certificate_id, force=False):
    """
    Schedule PDF rendering after the surrounding transaction commits.

    Rendering is deliberately outside certificate issuance so storage/PDF
    failures cannot roll back course completion or the certificate record.
    """
    transaction.on_commit(
        lambda: safely_render_certificate_pdf(certificate_id, force=force),
        robust=True
    )


def safely_render_certificate_pdf(certificate_id, force=False):
    try:
        return render_certificate_pdf(certificate_id, force=force)
    except Exception:
        logger.exception("Certificate PDF rendering failed for certificate %s", certificate_id)
        return None


def render_certificate_pdf(certificate_id, force=False):
    """
    Render and persist a certificate PDF idempotently.

    Args:
        certificate_id: Certificate primary key
        force: Regenerate even if a PDF already exists
    """
    from .models import Certificate

    certificate = Certificate.objects.select_related('user', 'course').get(id=certificate_id)
    if certificate_has_pdf(certificate) and not force:
        return certificate

    if force and certificate_has_pdf(certificate):
        certificate.pdf.delete(save=False)

    pdf_file = generate_certificate_pdf(certificate)
    certificate.pdf.save(pdf_file.name, pdf_file, save=False)
    certificate.save(update_fields=['pdf'])
    return certificate


def calculate_course_grade(user, course):
    """
    Calculate final course grade from completed, graded assessment evidence.

    Current certificate policy:
    - quiz score: best completed attempt per quiz
    - no graded assessment evidence: no grade (`None`)
    
    Args:
        user: User instance
        course: Course instance
    
    Returns:
        Decimal|None: Grade percentage (0-100), or None when there is no
        graded assessment evidence for the course.
    """
    from decimal import Decimal, ROUND_HALF_UP
    from assessments.models import QuizAttempt
    
    quiz_attempts = QuizAttempt.objects.filter(
        user=user,
        quiz__lesson__module__course=course,
        quiz__is_published=True,
        completed_at__isnull=False,
        score__isnull=False
    ).select_related('quiz')
    
    total_score = Decimal('0.0')
    total_possible = Decimal('0.0')
    best_quiz_attempts = {}

    for attempt in quiz_attempts:
        existing = best_quiz_attempts.get(attempt.quiz_id)
        if existing is None or attempt.score > existing.score:
            best_quiz_attempts[attempt.quiz_id] = attempt

    for attempt in best_quiz_attempts.values():
        quiz_total_value = attempt.total_marks_snapshot or attempt.quiz.total_marks
        quiz_total = Decimal(quiz_total_value)
        if quiz_total <= 0:
            continue
        score = max(Decimal('0.0'), min(attempt.score, quiz_total))
        total_score += score
        total_possible += quiz_total

    if total_possible > 0:
        return ((total_score / total_possible) * 100).quantize(
            Decimal('0.01'),
            rounding=ROUND_HALF_UP
        )
    
    return None


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
    
    try:
        return render_certificate_pdf(certificate_id, force=True)
    except Certificate.DoesNotExist:
        raise ValidationError(f"Certificate with ID {certificate_id} not found")
