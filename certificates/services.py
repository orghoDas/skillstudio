from django.db import transaction, IntegrityError

def issue_certificate(enrollment):
    from .models import Certificate
    from .pdf import generate_certificate_pdf

    try:
        with transaction.atomic():
            certificate, created = Certificate.objects.get_or_create(
                user=enrollment.user,
                course=enrollment.course
            )

            if not certificate.pdf:
                pdf_file = generate_certificate_pdf(certificate)
                certificate.pdf.save(pdf_file.name, pdf_file)

            return certificate

    except IntegrityError:
        # Another process created it simultaneously
        return Certificate.objects.get(
            user=enrollment.user,
            course=enrollment.course
        )
