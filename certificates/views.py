from django.http import FileResponse
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone

from .models import Certificate
from .serializers import (
    CertificateSerializer,
    CertificateListSerializer,
    CertificateVerificationSerializer
)
from .services import verify_certificate, regenerate_certificate_pdf


# ===========================
# Certificate Views
# ===========================

class MyCertificatesListView(generics.ListAPIView):
    """List all certificates for the authenticated user."""
    permission_classes = [IsAuthenticated]
    serializer_class = CertificateListSerializer
    
    def get_queryset(self):
        return Certificate.objects.filter(
            user=self.request.user
        ).select_related('course').order_by('-issued_at')


class MyCertificateDetailView(APIView):
    """Get certificate details for a specific course."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, course_id):
        certificate = get_object_or_404(
            Certificate,
            user=request.user,
            course_id=course_id
        )
        
        serializer = CertificateSerializer(certificate, context={'request': request})
        return Response(serializer.data)


class VerifyCertificateView(APIView):
    """Publicly verify a certificate by verification code."""
    authentication_classes = []
    permission_classes = [AllowAny]
    
    def get(self, request, code):
        certificate = verify_certificate(code)
        
        if not certificate:
            serializer = CertificateVerificationSerializer({
                'valid': False
            })
            return Response(serializer.data, status=status.HTTP_404_NOT_FOUND)
        
        # Get user name
        user_name = certificate.user.email
        if hasattr(certificate.user, 'profile') and certificate.user.profile:
            if certificate.user.profile.full_name:
                user_name = certificate.user.profile.full_name
        
        data = {
            'valid': True,
            'user_name': user_name,
            'course_title': certificate.course.title,
            'issued_at': certificate.issued_at,
            'completion_date': certificate.completion_date,
            'grade': certificate.grade,
            'certificate_id': certificate.certificate_id
        }
        
        serializer = CertificateVerificationSerializer(data)
        return Response(serializer.data)


class DownloadCertificateView(APIView):
    """Download certificate PDF for a completed course."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, course_id):
        certificate = get_object_or_404(
            Certificate,
            user=request.user,
            course_id=course_id
        )
        
        # Verify enrollment completion
        if certificate.enrollment and not certificate.enrollment.is_completed:
            return Response(
                {'error': 'Course not completed'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if PDF exists
        if not certificate.pdf:
            return Response(
                {'error': 'Certificate PDF not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Increment download count
        certificate.increment_download_count()
        
        # Return PDF file
        return FileResponse(
            certificate.pdf_file.open('rb'),
            as_attachment=True,
            filename=f"certificate_{certificate.course.slug}_{certificate.user.id}.pdf"
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def regenerate_certificate(request, course_id):
    """Regenerate certificate PDF (staff only)."""
    if not request.user.is_staff:
        return Response(
            {'error': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    certificate = get_object_or_404(
        Certificate,
        course_id=course_id
    )
    
    try:
        certificate = regenerate_certificate_pdf(certificate)
        serializer = CertificateSerializer(certificate, context={'request': request})
        return Response(serializer.data)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
