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
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, code):
        certificate = get_object_or_404(
            Certificate,
            certificate_code=code
        )

        return Response({
            "valid": True,
            "user": (
                certificate.user.profile.full_name
                if hasattr(certificate.user, "profile")
                else certificate.user.email
            ),
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

        if not certificate.pdf:
            return Response(
                {"detail": "Certificate PDF not available"},
                status=404
            )
        
        if not enrollment.is_completed:
            raise PermissionDenied("Course not completed")

        return FileResponse(
            certificate.pdf.open("rb"),
            as_attachment=True,
            filename=f"{certificate.course.slug}.pdf"
        )
