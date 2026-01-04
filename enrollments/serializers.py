from rest_framework import serializers
from django.db.models import Count, Q, F, FloatField, ExpressionWrapper, Sum
from .models import Enrollment, LessonProgress, Wishlist
from courses.models import Course, Module, Lesson


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
    
    def get_progress_percentage(self, obj):
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
    course_thumbnail = serializers.URLField(source='course.thumbnail_url', read_only=True)
    instructor_name = serializers.CharField(source='course.instructor.get_full_name', read_only=True)
    progress_percentage = serializers.SerializerMethodField()
    completed_lessons = serializers.SerializerMethodField()
    completed_lessons_count = serializers.SerializerMethodField()
    total_lessons_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Enrollment
        fields = [
            'id', 'course', 'course_title', 'course_slug', 'course_thumbnail',
            'instructor_name', 'status', 'is_completed',
            'enrolled_at', 'completed_at', 'progress_percentage',
            'completed_lessons', 'completed_lessons_count', 'total_lessons_count'
        ]
        read_only_fields = ['enrolled_at', 'completed_at']
    
    def get_course(self, obj):
        """Return minimal course information"""
        return {
            'id': obj.course.id,
            'title': obj.course.title,
            'slug': obj.course.slug,
            'thumbnail': obj.course.thumbnail
        }
    
    def get_progress_percentage(self, obj):
        total_lessons = Lesson.objects.filter(
            module__course=obj.course,
            is_free=False
        ).count()
        
        if total_lessons == 0:
            return 0
        
        completed_lessons = obj.lesson_progress.filter(is_completed=True).count()
        return round((completed_lessons / total_lessons) * 100, 2)
    
    def get_completed_lessons(self, obj):
        """Return list of completed lesson IDs"""
        return list(obj.lesson_progress.filter(is_completed=True).values_list('lesson_id', flat=True))
    
    def get_completed_lessons_count(self, obj):
        """Return count of completed lessons"""
        return obj.lesson_progress.filter(is_completed=True).count()
    
    def get_total_lessons_count(self, obj):
        """Return total lessons in course"""
        return Lesson.objects.filter(module__course=obj.course, is_free=False).count()


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
    
    def get_course(self, obj):
        course = obj.course
        instructor_name = course.instructor.email  
        if hasattr(course.instructor, 'profile') and course.instructor.profile.full_name:
            instructor_name = course.instructor.profile.full_name
            
        instructor_bio = ""
        if hasattr(course.instructor, 'profile') and course.instructor.profile.bio:
            instructor_bio = course.instructor.profile.bio
            
        return {
            'id': course.id,
            'title': course.title,
            'description': course.description,
            'thumbnail': course.thumbnail,
            'level': course.level,
            'instructor': {
                'id': course.instructor.id,
                'name': instructor_name,
                'bio': instructor_bio,
            }
        }
    
    def get_progress(self, obj):
        total_lessons = Lesson.objects.filter(
            module__course=obj.course,
            is_free=False
        ).count()
        
        completed_lessons = obj.lesson_progress.filter(is_completed=True).count()
        
        progress_percentage = 0
        if total_lessons > 0:
            progress_percentage = round((completed_lessons / total_lessons) * 100, 2)
        
        total_duration = Lesson.objects.filter(
            module__course=obj.course,
            is_free=False
        ).aggregate(total=Sum('duration_seconds'))['total'] or 0
        
        watched_time = obj.lesson_progress.aggregate(
            total=Sum('watch_time')
        )['total'] or 0
        
        return {
            'total_lessons': total_lessons,
            'completed_lessons': completed_lessons,
            'progress_percentage': progress_percentage,
            'total_duration_seconds': total_duration,
            'watched_time_seconds': watched_time,
        }
    
    def get_next_lesson(self, obj):
        """Get the next incomplete lesson."""
        lessons = Lesson.objects.filter(
            module__course=obj.course,
            is_free=False
        ).order_by('module__position', 'position')
        
        completed_ids = set(
            obj.lesson_progress.filter(is_completed=True).values_list('lesson_id', flat=True)
        )
        
        for lesson in lessons:
            if lesson.id not in completed_ids:
                return {
                    'id': lesson.id,
                    'title': lesson.title,
                    'module_id': lesson.module.id,
                    'module_title': lesson.module.title,
                    'position': lesson.position,
                }
        
        return None


class EnrollmentCreateSerializer(serializers.Serializer):
    """Serializer for creating enrollments."""
    course_id = serializers.IntegerField()
    
    def validate_course_id(self, value):
        if not Course.objects.filter(id=value, status='published').exists():
            raise serializers.ValidationError("Course not found or not published.")
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        course_id = validated_data['course_id']
        course = Course.objects.get(id=course_id)
        
        enrollment, created = Enrollment.objects.get_or_create(
            user=user,
            course=course,
            defaults={'status': 'active'}
        )
        
        # Reactivate if canceled
        if not created and enrollment.status == 'canceled':
            enrollment.status = 'active'
            enrollment.is_completed = False
            enrollment.completed_at = None
            enrollment.save()
        
        return enrollment


# ===========================
# 📋 Wishlist Serializers
# ===========================

class WishlistSerializer(serializers.ModelSerializer):
    """Wishlist serializer with course details."""
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_thumbnail = serializers.URLField(source='course.thumbnail', read_only=True)
    instructor_name = serializers.SerializerMethodField()
    course_price = serializers.DecimalField(source='course.price', max_digits=10, decimal_places=2, read_only=True)
    course_level = serializers.CharField(source='course.level', read_only=True)
    
    class Meta:
        model = Wishlist
        fields = [
            'id', 'course', 'course_title', 'course_thumbnail',
            'instructor_name', 'course_price', 'course_level', 'added_at'
        ]
        read_only_fields = ['added_at']
        
    def get_instructor_name(self, obj):
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
    course_title = serializers.CharField()
    total_lessons = serializers.IntegerField()
    completed_lessons = serializers.IntegerField()
    progress_percentage = serializers.FloatField()
    total_duration_seconds = serializers.IntegerField()
    watched_time_seconds = serializers.IntegerField()
    is_completed = serializers.BooleanField()
    enrolled_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)


        