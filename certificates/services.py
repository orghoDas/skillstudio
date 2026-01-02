# certificates/services/issue.py

from certificates.models import Certificate
from certificates.pdf import generate_certificate_pdf


def issue_certificate(enrollment):
    """
    Creates certificate + generates & stores PDF
    """

    # Prevent duplicates
    certificate, created = Certificate.objects.get_or_create(
        user=enrollment.user,
        course=enrollment.course,
        enrollment=enrollment
    )

    # Generate PDF only once
    if created or not certificate.pdf:
        pdf_file = generate_certificate_pdf(certificate)

        certificate.pdf.save(
            pdf_file.name,
            pdf_file,
            save=False
        )

        certificate.save(update_fields=["pdf"])

    return certificate