from io import BytesIO
from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from django.conf import settings
import qrcode


def generate_certificate_pdf(certificate):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4

    # 🎓 Title
    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width / 2, height - 140, "Certificate of Completion")

    # 👤 Student Name (SAFE)
    name = (
        certificate.user.profile.full_name
        if hasattr(certificate.user, "profile") and certificate.user.profile.full_name
        else certificate.user.email
    )

    c.setFont("Helvetica", 18)
    c.drawCentredString(width / 2, height - 240, name)

    # 📘 Course
    c.setFont("Helvetica", 14)
    c.drawCentredString(
        width / 2,
        height - 290,
        "has successfully completed the course"
    )

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(
        width / 2,
        height - 330,
        certificate.course.title
    )

    # 🔐 Verification Code
    c.setFont("Helvetica", 10)
    c.drawCentredString(
        width / 2,
        120,
        f"Verification Code: {certificate.certificate_code}"
    )

    # 🔗 QR → BACKEND VERIFY URL
    verify_url = (
        f"{settings.BACKEND_URL}/certificates/verify/"
        f"{certificate.certificate_code}/"
    )

    qr_img = qrcode.make(verify_url)
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer)
    qr_buffer.seek(0)

    c.drawImage(
        ImageReader(qr_buffer),
        width - 160,
        80,
        100,
        100
    )

    c.showPage()
    c.save()
    buffer.seek(0)

    return ContentFile(
        buffer.read(),
        name=f"certificate_{certificate.id}.pdf"
    )
