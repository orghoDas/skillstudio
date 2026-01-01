from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
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
            'certificate_id': certificate.certificate_id,
            'course': certificate.course.title,
            'issued_at': certificate.issued_at
        })
