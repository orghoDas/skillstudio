from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import InstructorProfile

User = get_user_model()


class InstructorProfileSerializer(serializers.ModelSerializer):
    """Serializer for instructor profile."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    total_revenue = serializers.DecimalField(max_digits=None, decimal_places=2, read_only=True)
    
    class Meta:
        model = InstructorProfile
        fields = [
            'id',
            'user',
            'user_email',
            'role',
            'bio',
            'headline',
            'website',
            'linkedin',
            'twitter',
            'expertise_areas',
            'years_of_experience',
            'certifications',
            'education',
            'total_courses',
            'total_students',
            'total_revenue',
            'is_verified',
            'verified_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'total_courses',
            'total_students',
            'total_revenue',
            'is_verified',
            'verified_at',
            'created_at',
            'updated_at',
        ]


class FeaturedInstructorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    headline = serializers.CharField(allow_blank=True)
    courses_count = serializers.IntegerField()
    students_count = serializers.IntegerField()


class InstructorDashboardSerializer(serializers.Serializer):
    """Serializer for instructor dashboard data."""
    
    total_courses = serializers.IntegerField()
    total_students = serializers.IntegerField()
    active_enrollments = serializers.IntegerField()
    total_revenue = serializers.FloatField()
    courses = serializers.ListField(child=serializers.DictField())
    students = serializers.ListField()
    revenue = serializers.DictField()
    payouts = serializers.ListField()


class InstructorRosterEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    course = serializers.DictField()
    enrolled_at = serializers.DateTimeField()
    progress = serializers.FloatField()
    status = serializers.CharField()
    last_accessed = serializers.DateTimeField()
