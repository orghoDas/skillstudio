from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import FileResponse
from django.shortcuts import get_object_or_404, render
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdmin
from accounts.utils import public_learner_name
from .models import Certificate, SupersededCertificateCode
from .serializers import CertificateListSerializer, CertificateSerializer, CertificateVerificationSerializer
from .services import ensure_certificate_pdf, regenerate_certificate_pdf, verify_certificate


class MyCertificatesListView(generics.ListAPIView):
    """List certificates belonging to the signed-in account."""
    permission_classes = [IsAuthenticated]
    serializer_class = CertificateListSerializer

    def get_queryset(self):
        unreleased = Certificate.unreleased_exam_attempts(
            self.request.user.pk, OuterRef('course_id'), OuterRef('issued_at'),
        )
        return Certificate.objects.filter(user=self.request.user).select_related('course', 'enrollment', 'user__profile').annotate(
            has_unreleased_exam_grades=Exists(unreleased),
        )


class MyCertificateDetailView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CertificateSerializer

    def get(self, request, course_id):
        certificate = get_object_or_404(
            Certificate.objects.select_related('user__profile', 'course', 'enrollment'),
            user=request.user, course_id=course_id,
        )
        return Response(CertificateSerializer(certificate, context={'request': request}).data)


def verification_details(code):
    try:
        certificate = verify_certificate(code)
    except ValidationError:
        superseded = SupersededCertificateCode.objects.filter(pk=code).first()
        if superseded:
            return {
                'valid': False, 'revoked': True, 'revoked_at': superseded.revoked_at,
                'reason': 'superseded', 'code': 'superseded',
                'detail': 'This certificate was superseded by a newer copy.',
            }, status.HTTP_410_GONE
        return {'valid': False}, status.HTTP_404_NOT_FOUND
    if certificate.is_revoked:
        return {'valid': False, 'revoked': True, 'revoked_at': certificate.revoked_at}, status.HTTP_410_GONE
    return {
        'valid': True,
        'id': certificate.pk,
        'user_name': public_learner_name(certificate.user),
        'course_title': certificate.course.title,
        'issued_at': certificate.issued_at,
        'completion_date': certificate.completion_date,
        'grade': certificate.released_grade,
    }, status.HTTP_200_OK


def certificate_verification_page(request, code):
    details, response_status = verification_details(code)
    return render(request, 'certificates/verify.html', {'certificate': details}, status=response_status)


class VerifyCertificateView(APIView):
    """Public verification endpoint, including links from older PDFs."""
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = CertificateVerificationSerializer

    def get(self, request, code):
        details, response_status = verification_details(code)
        return Response(CertificateVerificationSerializer(details).data, status=response_status)


class DownloadCertificateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    @extend_schema(responses={(200, 'application/pdf'): OpenApiTypes.BINARY})
    def get(self, request, certificate_id=None, course_id=None):
        certificates = Certificate.objects.select_for_update(of=('self',)).select_related('course', 'enrollment')
        lookup = {'pk': certificate_id} if certificate_id is not None else {'course_id': course_id}
        certificate = get_object_or_404(certificates, user=request.user, **lookup)
        if certificate.is_revoked:
            return Response({'detail': 'This certificate was revoked.'}, status=status.HTTP_410_GONE)
        if certificate.enrollment and not certificate.enrollment.is_completed:
            return Response({'detail': 'Course not completed.'}, status=status.HTTP_403_FORBIDDEN)

        certificate = ensure_certificate_pdf(certificate)
        if certificate is None:
            return Response(
                {'detail': 'The certificate PDF could not be generated right now. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            pdf = certificate.pdf.open('rb')
        except FileNotFoundError:
            return Response({'detail': 'The certificate PDF is unavailable.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        certificate.increment_download_count()
        return FileResponse(pdf, as_attachment=True, filename=f"certificate_{certificate.course.slug}.pdf")


@extend_schema(request=None, responses=CertificateSerializer)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
@transaction.atomic
def regenerate_certificate(request, certificate_id):
    """Regenerate exactly the certificate identified in the route."""
    certificate = get_object_or_404(
        Certificate.objects.select_for_update(of=('self',)).select_related('enrollment'), pk=certificate_id,
    )
    if certificate.is_revoked:
        return Response({'detail': 'This certificate was revoked.'}, status=status.HTTP_410_GONE)
    certificate = regenerate_certificate_pdf(certificate_id, request.user)
    return Response(CertificateSerializer(certificate, context={'request': request}).data)
