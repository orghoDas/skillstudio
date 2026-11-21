from functools import lru_cache
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont, shapeStr
from reportlab.pdfgen import canvas
import qrcode

from accounts.utils import profile_display_name


FONT_DIR = Path(__file__).with_name('fonts')


@lru_cache(maxsize=1)
def _register_fonts():
    fonts = (
        ('CertificateSans', 'NotoSans-Regular.ttf'),
        ('CertificateBold', 'NotoSans-Bold.ttf'),
        ('CertificateBengali', 'NotoSansBengali-Regular.ttf'),
        ('CertificateDevanagari', 'NotoSansDevanagari-Regular.ttf'),
    )
    for name, file_name in fonts:
        pdfmetrics.registerFont(TTFont(name, FONT_DIR / file_name))


def _draw_text(pdf, text, width, top, max_height, font_size, *, bold=False):
    primary = 'CertificateBold' if bold else 'CertificateSans'
    candidates = (primary, 'CertificateBengali', 'CertificateDevanagari')
    coverage = [(name, pdfmetrics.getFont(name).face.charToGlyph) for name in candidates]

    def font_for_word(word):
        return next((name for name, glyphs in coverage if all(ord(char) in glyphs for char in word)), primary)

    words = [(word, font_for_word(word)) for word in text.split()]
    max_width = width - 100
    for size in range(font_size, 8, -1):
        space = pdfmetrics.stringWidth(' ', primary, size)
        lines = []
        line = []
        line_width = 0
        for word, font in words:
            shaped = shapeStr(word, font, size)
            positions = getattr(shaped, '__shapeData__', None)
            natural_width = (
                sum(item.x_advance for item in positions) * size / 1000
                if positions else pdfmetrics.stringWidth(word, font, size)
            )
            advance = min(natural_width, max_width)
            if line and line_width + space + advance > max_width:
                lines.append((line, line_width))
                line = []
                line_width = 0
            if line:
                line_width += space
            line.append((shaped, font, advance, natural_width))
            line_width += advance
        if line:
            lines.append((line, line_width))
        leading = size * 1.4
        if leading * len(lines) > max_height:
            continue

        for index, (line, line_width) in enumerate(lines):
            x = (width - line_width) / 2
            y = top - size - index * leading
            for word, font, advance, natural_width in line:
                run = pdf.beginText(x, y)
                run.setFont(font, size)
                run.setHorizScale(advance / natural_width * 100 if natural_width > advance else 100)
                run.textLine(word)
                pdf.drawText(run)
                x += advance + space
        return


def generate_certificate_pdf(certificate):
    _register_fonts()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    pdf.setTitle('Certificate of Completion')

    name = profile_display_name(certificate.user) or certificate.user.email
    _draw_text(pdf, 'Certificate of Completion', width, height - 105, 55, 28, bold=True)
    _draw_text(pdf, name, width, height - 185, 95, 24)
    _draw_text(pdf, 'has successfully completed the course', width, height - 292, 30, 14)
    _draw_text(pdf, certificate.course.title, width, height - 330, 150, 20, bold=True)
    grade = certificate.released_grade
    if grade is not None:
        _draw_text(pdf, f'Grade: {grade:.2f}%', width, height - 490, 30, 13)
    _draw_text(pdf, f'Certificate ID: {certificate.pk}', width, 106, 40, 10)

    qr_buffer = BytesIO()
    qrcode.make(certificate.verification_url).save(qr_buffer)
    qr_buffer.seek(0)
    pdf.drawImage(ImageReader(qr_buffer), (width - 96) / 2, 117, 96, 96)

    pdf.showPage()
    pdf.save()
    return ContentFile(buffer.getvalue(), name=f'certificate_{certificate.pk}.pdf')
