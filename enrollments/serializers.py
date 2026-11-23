from decimal import Decimal
from accounts.utils import public_instructor_name
from rest_framework import serializers
from django.db.models import Sum
from .models import Enrollment, LessonProgress, Wishlist
from courses.models import Course, Lesson
from courses.policies import can_view_course_catalog
from .constants import ACCESS_STATUSES
from .services import get_lesson_completion_stats, get_resume_lesson, lesson_progress_percentage


# ===========================
# 🎯 LessonProgress Serializers
# ===========================

class LessonProgressSerializer(serializers.ModelSerializer):
    """Basic lesson progress serializer."""
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    module_title = serializers.CharField(source='lesson.module.title', read_only=True)
    
    class Meta:
        model = LessonProgress
        fields = [
            'id', 'lesson', 'lesson_title', 'module_title',
            'watch_time', 'is_completed', 'completed_at', 'started_at'
        ]
        read_only_fields = ['started_at']


class LessonProgressDetailSerializer(serializers.ModelSerializer):
    """Detailed lesson progress with lesson information."""
    lesson = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = LessonProgress
        fields = [
            'id', 'lesson', 'watch_time', 'is_completed',
            'completed_at', 'progress_percentage', 'started_at'
        ]
        read_only_fields = ['started_at']
    
    def get_lesson(self, obj):
        return {
            'id': obj.lesson.id,
            'title': obj.lesson.title,
            'duration_seconds': obj.lesson.duration_seconds,
            'module_id': obj.lesson.module.id,
            'module_title': obj.lesson.module.title,
            'position': obj.lesson.position,
        }
    
    def get_progress_percentage(self, obj) -> float:
        if obj.lesson.duration_seconds == 0:
            return 0
        return round((obj.watch_time / obj.lesson.duration_seconds) * 100, 2)


# ===========================
# 🎓 Enrollment Serializers
# ===========================

class EnrollmentListSerializer(serializers.ModelSerializer):
    """List serializer for enrollments."""
    course = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    course_thumbnail = serializers.URLField(source='course.thumbnail', read_only=True, allow_null=True)
    instructor_name = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    completed_lessons = serializers.SerializerMethodField()
    completed_lessons_count = serializers.SerializerMethodField()
    total_lessons_count = serializers.IntegerField(source='required_count', read_only=True)
    
    class Meta:
        model = Enrollment
        fields = [
            'id', 'course', 'course_title', 'course_slug', 'course_thumbnail',
            'instructor_name', 'status', 'is_completed',
            'enrolled_at', 'completed_at', 'progress_percentage',
            'completed_lessons', 'completed_lessons_count', 'total_lessons_count'
        ]
        read_only_fields = ['enrolled_at', 'completed_at']
    
    def get_instructor_name(self, obj) -> str:
        return public_instructor_name(obj.course.instructor)

    def get_course(self, obj) -> dict:
        """Return minimal course information"""
        return {
            'id': obj.course.id,
            'title': obj.course.title,
            'slug': obj.course.slug,
            'thumbnail': obj.course.thumbnail
        }
    
    def get_progress_percentage(self, obj) -> float:
        return lesson_progress_percentage(len(obj.completed_required_progress), obj.required_count)
    
    def get_completed_lessons(self, obj) -> list[int]:
        """Return list of completed lesson IDs"""
        return [progress.lesson_id for progress in obj.completed_required_progress]
    
    def get_completed_lessons_count(self, obj) -> int:
        """Return count of completed lessons"""
        return len(obj.completed_required_progress)


class EnrollmentDetailSerializer(serializers.ModelSerializer):
    """Detailed enrollment with full course and progress information."""
    course = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    next_lesson = serializers.SerializerMethodField()
    
    class Meta:
        model = Enrollment
        fields = [
            'id', 'course', 'status', 'is_completed',
            'enrolled_at', 'completed_at', 'progress', 'next_lesson'
        ]
        read_only_fields = ['enrolled_at', 'completed_at']
    
    def get_course(self, obj) -> dict:
        course = obj.course
        instructor = course.instructor
        profile = getattr(instructor, 'profile', None)

        return {
            'id': course.id,
            'title': course.title,
            'description': course.description,
            'thumbnail': course.thumbnail,
            'level': course.level,
            'instructor': {
                'id': instructor.id,
                'name': public_instructor_name(instructor),
                'bio': (profile.bio or '') if profile else '',
            }
        }
    
    def get_progress(self, obj) -> dict:
        stats = get_lesson_completion_stats(obj)
        
        total_duration = Lesson.objects.filter(
            module__course=obj.course,
            is_free=False
        ).aggregate(total=Sum('duration_seconds'))['total'] or 0
        
        watched_time = obj.lesson_progress.aggregate(
            total=Sum('watch_time')
        )['total'] or 0
        
        return {
            'total_lessons': stats['total_lessons'],
            'completed_lessons': stats['completed_lessons'],
            'progress_percentage': stats['progress_percentage'],
            'total_duration_seconds': total_duration,
            'watched_time_seconds': watched_time,
        }
    
    def get_next_lesson(self, obj) -> dict | None:
        """Get the next incomplete lesson."""
        if obj.status not in ACCESS_STATUSES or not can_view_course_catalog(obj.user, obj.course):
            return None
        lesson = get_resume_lesson(obj)
        if lesson is None:
            return None
        return {
            'id': lesson.id,
            'title': lesson.title,
            'module_id': lesson.module_id,
            'module_title': lesson.module.title,
            'position': lesson.position,
        }


class EnrollmentCreateSerializer(serializers.Serializer):
    """Input for enrolling in (buying) a course.

    The purchase itself — pricing, wallet debit, instructor credit, Payment
    record, coupon redemption and the enrollment — happens atomically in
    ``payments.services.purchase_course``. A client may cap what it authorizes;
    the service still determines the price.
    """
    course_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    coupon_code = serializers.CharField(max_length=64, required=False, allow_blank=True)
    max_charge = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.00'), required=False,
    )

    def create(self, validated_data):
        """Kept for callers that use ``serializer.save()``; returns the enrollment."""
        from payments.services import PurchaseError, purchase_course

        try:
            result = purchase_course(
                self.context['request'].user,
                validated_data['course_id'],
                coupon_code=validated_data.get('coupon_code') or None,
                max_charge=validated_data.get('max_charge'),
            )
        except PurchaseError as exc:
            raise serializers.ValidationError({"detail": exc.message, "code": exc.code})
        return result.enrollment


# ===========================
# 📋 Wishlist Serializers
# ===========================

class WishlistSerializer(serializers.ModelSerializer):
    """Wishlist serializer with course details."""
    course_slug = serializers.SlugField(source='course.slug', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_thumbnail = serializers.URLField(source='course.thumbnail', read_only=True)
    instructor_name = serializers.SerializerMethodField()
    course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)
    course_level = serializers.CharField(source='course.level', read_only=True)
    
    class Meta:
        model = Wishlist
        fields = [
            'id', 'course', 'course_slug', 'course_title', 'course_thumbnail',
            'instructor_name', 'course_price', 'course_level', 'added_at'
        ]
        read_only_fields = ['added_at']
        
    def get_instructor_name(self, obj) -> str:
        if hasattr(obj.course.instructor, 'profile') and obj.course.instructor.profile.full_name:
            return obj.course.instructor.profile.full_name
        return obj.course.instructor.email


class WishlistCreateSerializer(serializers.Serializer):
    """Serializer for adding courses to wishlist."""
    course_id = serializers.IntegerField()
    
    def validate_course_id(self, value):
        if not Course.objects.filter(id=value, status='published').exists():
            raise serializers.ValidationError("Course not found or not published.")
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        course_id = validated_data['course_id']
        course = Course.objects.get(id=course_id)
        
        wishlist, created = Wishlist.objects.get_or_create(
            user=user,
            course=course
        )
        
        return wishlist


# ===========================
# 📊 Statistics Serializers
# ===========================

class EnrollmentStatsSerializer(serializers.Serializer):
    """Serializer for enrollment statistics."""
    total_enrollments = serializers.IntegerField()
    active_enrollments = serializers.IntegerField()
    completed_enrollments = serializers.IntegerField()
    canceled_enrollments = serializers.IntegerField()
    total_courses_enrolled = serializers.IntegerField()
    average_progress = serializers.FloatField()
    total_watch_time_hours = serializers.FloatField()


class CourseProgressStatsSerializer(serializers.Serializer):
    """Serializer for detailed course progress statistics."""
    course_id = serializers.IntegerField()
    course_title = serializers.CharField(source='course.title')
    total_lessons = serializers.IntegerField(source='required_count')
    completed_lessons = serializers.IntegerField(source='required_completed_count')
    progress_percentage = serializers.SerializerMethodField()
    total_duration_seconds = serializers.IntegerField()
    watched_time_seconds = serializers.IntegerField()
    is_completed = serializers.BooleanField()
    enrolled_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)

    def get_progress_percentage(self, obj) -> float:
        return lesson_progress_percentage(obj.required_completed_count, obj.required_count)
