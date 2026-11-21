import logging

from uuid import uuid4

from django.db import transaction
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from accounts.utils import is_platform_admin

# Import PDF generation function
from .pdf import generate_certificate_pdf

logger = logging.getLogger(__name__)


@transaction.atomic
def issue_certificate(user, course):
    """Issue a certificate for a completed enrollment. Render its PDF on demand."""
    from .models import Certificate
    from enrollments.models import Enrollment

    try:
        enrollment = Enrollment.objects.select_for_update().get(user=user, course=course)
    except Enrollment.DoesNotExist as exc:
        raise ValidationError("User is not enrolled in this course.") from exc
    if enrollment.status == 'canceled':
        raise ValidationError("Cannot issue a certificate for a canceled enrollment.")
    if not enrollment.is_completed:
        raise ValidationError("Enrollment must be completed to issue a certificate.")

    certificate = Certificate.objects.filter(user=user, course=course).first()
    if certificate is not None and not certificate.is_revoked:
        return certificate

    fields = {
        'enrollment': enrollment,
        'completion_date': enrollment.completed_at or timezone.now(),
        'grade': calculate_course_grade(user, course),
    }
    if certificate is None:
        return Certificate.objects.create(user=user, course=course, **fields)

    previous_name = certificate.pdf.name
    storage = certificate.pdf.storage
    fields.update(
        verification_code=str(uuid4()), issued_at=timezone.now(),
        revoked_at=None, pdf=None, pdf_verification_url='', pdf_grade=None,
    )
    for field, value in fields.items():
        setattr(certificate, field, value)
    certificate.save(update_fields=fields)
    if previous_name:
        transaction.on_commit(lambda: storage.delete(previous_name), robust=True)
    return certificate


def certificate_has_pdf(certificate):
    """True only if the PDF is recorded AND the file really exists in storage
    (OPS-02: a recorded name whose file was deleted used to 500 on download)."""
    try:
        name = (certificate.pdf.name or "").strip()
        return bool(name) and certificate.pdf.storage.exists(name)
    except (ValueError, AttributeError):
        return False


def ensure_certificate_pdf(certificate):
    """Return a certificate whose PDF file exists, rendering it now if missing.

    Returns None if rendering fails (the error is logged).
    """
    if (
        certificate.pdf_verification_url == certificate.verification_url
        and certificate.pdf_grade == certificate.released_grade
        and certificate_has_pdf(certificate)
    ):
        return certificate
    rendered = safely_render_certificate_pdf(certificate.id)
    if rendered is None or not certificate_has_pdf(rendered):
        return None
    return rendered


def safely_render_certificate_pdf(certificate_id, force=False):
    try:
        return render_certificate_pdf(certificate_id, force=force)
    except Exception:
        logger.exception("Certificate PDF rendering failed for certificate %s", certificate_id)
        return None


@transaction.atomic
def render_certificate_pdf(certificate_id, force=False):
    """
    Render and persist a certificate PDF idempotently.

    Args:
        certificate_id: Certificate primary key
        force: Regenerate even if a PDF already exists
    """
    from .models import Certificate

    certificate = Certificate.objects.select_for_update(of=('self',)).select_related(
        'user__profile', 'course', 'enrollment',
    ).get(pk=certificate_id)
    if certificate.is_revoked:
        raise ValidationError("Revoked certificates cannot be rendered.")
    verification_url = certificate.verification_url
    grade = certificate.released_grade
    if (
        not force and certificate.pdf_verification_url == verification_url
        and certificate.pdf_grade == grade and certificate_has_pdf(certificate)
    ):
        return certificate

    previous_name = certificate.pdf.name
    storage = certificate.pdf.storage
    pdf_file = generate_certificate_pdf(certificate)
    certificate.pdf.save(pdf_file.name, pdf_file, save=False)
    certificate.pdf_verification_url = verification_url
    certificate.pdf_grade = grade
    certificate.save(update_fields=['pdf', 'pdf_verification_url', 'pdf_grade'])
    if previous_name and previous_name != certificate.pdf.name:
        transaction.on_commit(lambda: storage.delete(previous_name), robust=True)
    return certificate


def calculate_course_grade(user, course):
    """
    Calculate final course grade from completed, graded assessment evidence.

    Current certificate policy:
    - best completed attempt per published quiz and exam
    - each assessment contributes the points earned and possible in that attempt
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
    from exams.services import graded_course_exam_attempts
    
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

    best_exams = {}
    for attempt in graded_course_exam_attempts(user, course):
        possible = attempt.grading_total_marks
        if possible <= 0:
            continue
        score = max(Decimal('0.0'), min(attempt.score, possible))
        previous = best_exams.get(attempt.exam_id)
        if previous is None or score / possible > previous[0] / previous[1]:
            best_exams[attempt.exam_id] = (score, possible)
    for score, possible in best_exams.values():
        total_score += score
        total_possible += possible

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
            'user__profile', 'course', 'enrollment'
        ).get(verification_code=verification_code)
    except Certificate.DoesNotExist:
        raise ValidationError(f"Invalid or non-existent verification code")


def regenerate_certificate_pdf(certificate_id, user):
    """
    Regenerate PDF for an existing certificate.
    
    Args:
        certificate_id: Certificate ID
        user: Platform administrator requesting regeneration
    
    Returns:
        Updated Certificate instance
        
    Raises:
        PermissionDenied: If user is not a platform administrator
        ValidationError: If certificate not found
    """
    from .models import Certificate
    
    # Check permission
    if not is_platform_admin(user):
        raise PermissionDenied("Only platform administrators can regenerate certificate PDFs")
    
    try:
        return render_certificate_pdf(certificate_id, force=True)
    except Certificate.DoesNotExist:
        raise ValidationError(f"Certificate with ID {certificate_id} not found")
