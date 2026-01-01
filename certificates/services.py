import uuid
from .models import Certificate


def issue_certificate(enrollment):
    if not enrollment.is_completed:
        return None

    certificate, created = Certificate.objects.get_or_create(
        user=enrollment.user,
        course=enrollment.course,
        enrollment=enrollment,
        defaults={
            'certificate_id': uuid.uuid4().hex
        }
    )

    return certificate
