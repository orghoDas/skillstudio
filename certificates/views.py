from django.http import FileResponse
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Certificate


class MyCertificateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        certificate = get_object_or_404(
            Certificate,
            user=request.user,
            course_id=course_id
        )

        return Response({
            'certificate_id': str(certificate.certificate_id),
            'course': certificate.course.title,
            'issued_at': certificate.issued_at,
})
    

class VerifyCertificateView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, code):
        certificate = get_object_or_404(
            Certificate,
            certificate_id=code
        )

        return Response({
            "valid": True,
            "user": certificate.user.get_full_name(),
            "course": certificate.course.title,
            "issued_at": certificate.issued_at
        })
    

class DownloadCertificateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, course_id):
        certificate = get_object_or_404(
            Certificate,
            user=request.user,
            course_id=course_id,
            enrollment__is_completed=True
)

        return FileResponse(
            certificate.pdf.open(),
            as_attachment=True,
            filename=f"{certificate.course.title}.pdf"
)
