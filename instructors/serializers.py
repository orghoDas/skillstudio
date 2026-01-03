from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import InstructorProfile, InstructorPayout

User = get_user_model()


class InstructorProfileSerializer(serializers.ModelSerializer):
    """Serializer for instructor profile."""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = InstructorProfile
        fields = [
            'id',
            'user',
            'user_email',
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
            'average_rating',
            'total_reviews',
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
            'average_rating',
            'total_reviews',
            'is_verified',
            'verified_at',
            'created_at',
            'updated_at',
        ]


class InstructorPayoutSerializer(serializers.ModelSerializer):
    """Serializer for instructor payouts."""
    
    instructor_email = serializers.EmailField(source='instructor.email', read_only=True)
    
    class Meta:
        model = InstructorPayout
        fields = [
            'id',
            'instructor',
            'instructor_email',
            'amount',
            'currency',
            'status',
            'payment_method',
            'payment_details',
            'transaction_id',
            'processed_at',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'instructor',
            'status',
            'transaction_id',
            'processed_at',
            'created_at',
            'updated_at',
        ]


class InstructorPayoutListSerializer(serializers.ModelSerializer):
    """Simplified serializer for payout lists."""
    
    class Meta:
        model = InstructorPayout
        fields = [
            'id',
            'amount',
            'currency',
            'status',
            'created_at',
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
    avg_rating = serializers.DecimalField(max_digits=3, decimal_places=2, allow_null=True)


class StudentEngagementSerializer(serializers.Serializer):
    """Serializer for student engagement data."""
    
    student_id = serializers.IntegerField()
    student_email = serializers.EmailField()
    course = serializers.CharField()
    completed_lessons = serializers.IntegerField()
    last_activity = serializers.DateTimeField(allow_null=True)
