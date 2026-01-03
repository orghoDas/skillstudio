from rest_framework import serializers
from .models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    """Serializer for Certificate model."""
    
    user_name = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    verification_url = serializers.ReadOnlyField()
    pdf_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Certificate
        fields = [
            'id',
            'certificate_id',
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
            'pdf_url'
        ]
        read_only_fields = ['id', 'certificate_id', 'verification_code', 'issued_at']
    
    def get_user_name(self, obj):
        """Get user's full name or email."""
        if hasattr(obj.user, 'profile') and obj.user.profile and obj.user.profile.full_name:
            return obj.user.profile.full_name
        return obj.user.email
    
    def get_pdf_url(self, obj):
        """Get PDF download URL."""
        if obj.pdf:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pdf.url)
            return obj.pdf.url
        return None


class CertificateListSerializer(serializers.ModelSerializer):
    """Simplified serializer for certificate lists."""
    
    course_title = serializers.CharField(source='course.title', read_only=True)
    has_pdf = serializers.SerializerMethodField()
    
    class Meta:
        model = Certificate
        fields = [
            'id',
            'certificate_id',
            'course_title',
            'grade',
            'issued_at',
            'has_pdf'
        ]
    
    def get_has_pdf(self, obj):
        """Check if PDF exists."""
        return bool(obj.pdf)


class CertificateVerificationSerializer(serializers.Serializer):
    """Serializer for certificate verification response."""
    
    valid = serializers.BooleanField()
    user_name = serializers.CharField(required=False)
    course_title = serializers.CharField(required=False)
    issued_at = serializers.DateTimeField(required=False)
    completion_date = serializers.DateTimeField(required=False)
    grade = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    certificate_id = serializers.UUIDField(required=False)
