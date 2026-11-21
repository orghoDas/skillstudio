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


class InstructorDashboardSerializer(serializers.Serializer):
    """Serializer for instructor dashboard data."""
    
    courses = serializers.ListField()
    students = serializers.ListField()
    revenue = serializers.DictField()
    payouts = serializers.ListField()


class CourseOverviewSerializer(serializers.Serializer):
    """Serializer for course overview in dashboard."""
    
    id = serializers.IntegerField()
    title = serializers.CharField()
    enrollments = serializers.IntegerField()


class StudentEngagementSerializer(serializers.Serializer):
    """Serializer for student engagement data."""
    
    student_id = serializers.IntegerField()
    student_email = serializers.EmailField()
    course = serializers.CharField()
    completed_lessons = serializers.IntegerField()
    last_activity = serializers.DateTimeField(allow_null=True)
