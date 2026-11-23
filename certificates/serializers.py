from rest_framework import serializers
from django.urls import reverse
from .models import Certificate
from accounts.utils import public_learner_name


class CertificateSerializer(serializers.ModelSerializer):
    """Serializer for Certificate model."""
    
    user_name = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    verification_url = serializers.ReadOnlyField()
    pdf_url = serializers.SerializerMethodField()
    is_revoked = serializers.BooleanField(read_only=True)
    grade = serializers.DecimalField(source='released_grade', max_digits=5, decimal_places=2, read_only=True)
    
    class Meta:
        model = Certificate
        fields = [
            'id',
            'verification_code',
            'user_name',
            'course_title',
            'course_slug',
            'grade',
            'completion_date',
            'issued_at',
            'download_count',
            'last_downloaded_at',
            'verification_url',
            'is_revoked',
            'revoked_at',
            'pdf_url'
        ]
        read_only_fields = ['id', 'verification_code', 'issued_at', 'revoked_at']
    
    def get_user_name(self, obj) -> str:
        return public_learner_name(obj.user)
    
    def get_pdf_url(self, obj) -> str | None:
        """Get PDF download URL."""
        if obj.is_revoked:
            return None
        path = reverse('download-certificate', kwargs={'certificate_id': obj.pk})
        request = self.context.get('request')
        return request.build_absolute_uri(path) if request else path


class CertificateListSerializer(serializers.ModelSerializer):
    """Simplified serializer for certificate lists."""
    
    course_title = serializers.CharField(source='course.title', read_only=True)
    has_pdf = serializers.SerializerMethodField()
    verification_url = serializers.ReadOnlyField()
    is_revoked = serializers.BooleanField(read_only=True)
    grade = serializers.DecimalField(source='released_grade', max_digits=5, decimal_places=2, read_only=True)
    
    class Meta:
        model = Certificate
        fields = [
            'id',
            'course_title',
            'grade',
            'issued_at',
            'verification_url',
            'is_revoked',
            'has_pdf'
        ]
    
    def get_has_pdf(self, obj) -> bool:
        return (
            not obj.is_revoked and bool(obj.pdf)
            and obj.pdf_verification_url == obj.verification_url and obj.pdf_grade == obj.released_grade
            and obj.pdf_learner_name == public_learner_name(obj.user)
        )


class CertificateVerificationSerializer(serializers.Serializer):
    """Serializer for certificate verification response."""
    
    valid = serializers.BooleanField()
    user_name = serializers.CharField(required=False)
    course_title = serializers.CharField(required=False)
    issued_at = serializers.DateTimeField(required=False)
    completion_date = serializers.DateTimeField(required=False)
    grade = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    id = serializers.UUIDField(required=False)
    revoked = serializers.BooleanField(required=False)
    reason = serializers.CharField(required=False)
    detail = serializers.CharField(required=False)
    code = serializers.CharField(required=False)
    revoked_at = serializers.DateTimeField(required=False, allow_null=True)
