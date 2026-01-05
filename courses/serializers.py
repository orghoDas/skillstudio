from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from .models import (
    Course, Lesson, Module, Category, Tag, CourseTag,
    CourseVersion, LessonResource
)

User = get_user_model()


# ===== CATEGORY & TAG SERIALIZERS =====

class CategorySerializer(serializers.ModelSerializer):
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'course_count']
        read_only_fields = ['slug']

    def get_course_count(self, obj):
        return obj.courses.filter(status='published').count()


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']


# ===== LESSON SERIALIZERS =====

class LessonResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonResource
        fields = ['id', 'file_url', 'resource_type', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class LessonSerializer(serializers.ModelSerializer):
    resources = LessonResourceSerializer(many=True, read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'module', 'title', 'content_type', 'content_text',
            'video_url', 'duration_seconds', 'metadata', 'position',
            'is_free', 'view_count', 'created_at', 'resources'
        ]
        read_only_fields = ['view_count', 'created_at']


class LessonCreateUpdateSerializer(serializers.ModelSerializer):
    module = serializers.PrimaryKeyRelatedField(queryset=Module.objects.all(), required=False)
    content_text = serializers.CharField(required=False, allow_blank=True, default='')
    video_url = serializers.URLField(required=False, allow_blank=True, default='')
    duration_seconds = serializers.IntegerField(required=False, allow_null=True, default=0)
    metadata = serializers.JSONField(required=False, allow_null=True, default=None)
    position = serializers.IntegerField(required=False, default=0)
    is_free = serializers.BooleanField(required=False, default=False)
    
    class Meta:
        model = Lesson
        fields = [
            'module', 'title', 'content_type', 'content_text',
            'video_url', 'duration_seconds', 'metadata', 'position', 'is_free'
        ]

    def validate(self, attrs):
        # Allow all content types - validation is optional
        # Instructors can add video URLs and content later
        return attrs


class LessonDataSerializer(serializers.ModelSerializer):
    resources = LessonResourceSerializer(many=True, read_only=True)
    module_title = serializers.CharField(source='module.title', read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'content_type', 'content_text', 'video_url',
            'metadata', 'position', 'created_at', 'duration_seconds',
            'is_free', 'resources', 'module_title'
        ]


class LessonListSerializer(serializers.ModelSerializer):
    is_completed = serializers.BooleanField(read_only=True)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'position', 'is_free', 'content_type',
            'duration_seconds', 'is_completed', 'is_locked'
        ]


class CurriculumLessonSerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'position', 'is_free', 'content_type',
            'duration_seconds', 'is_completed', 'is_locked'
        ]

    def get_is_completed(self, lesson):
        return lesson.id in self.context.get('completed_ids', set())

    def get_is_locked(self, lesson):
        if lesson.is_free:
            return False
        return lesson.id in self.context.get('locked_ids', set())


# ===== MODULE SERIALIZERS =====

class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'position', 'created_at', 'lessons', 'lesson_count']
        read_only_fields = ['created_at']

    def get_lesson_count(self, obj):
        return obj.lessons.count()


class ModuleCreateUpdateSerializer(serializers.ModelSerializer):
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), required=False)
    
    class Meta:
        model = Module
        fields = ['course', 'title', 'position']


class CurriculumModuleSerializer(serializers.ModelSerializer):
    lessons = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'title', 'position', 'lessons']

    def get_lessons(self, module):
        lessons = module.lessons.order_by('position')
        return CurriculumLessonSerializer(
            lessons,
            many=True,
            context=self.context
        ).data


# ===== COURSE SERIALIZERS =====

class CourseListSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.profile.full_name', read_only=True)
    instructor_email = serializers.EmailField(source='instructor.email', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    enrollments_count = serializers.SerializerMethodField()
    module_count = serializers.SerializerMethodField()
    lesson_count = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'thumbnail', 'price',
            'is_free', 'status', 'level', 'instructor_name', 'instructor_email',
            'category_name', 'published_at', 'created_at', 'enrollments_count',
            'module_count', 'lesson_count', 'average_rating', 'reviews_count'
        ]

    def get_enrollments_count(self, obj):
        return obj.enrollments.filter(status='active').count()

    def get_module_count(self, obj):
        return obj.modules.count()

    def get_lesson_count(self, obj):
        return Lesson.objects.filter(module__course=obj).count()
    
    def get_average_rating(self, obj):
        # Return 0 if no reviews exist
        from social.models import Review
        avg = Review.objects.filter(course=obj).aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0
    
    def get_reviews_count(self, obj):
        from social.models import Review
        return Review.objects.filter(course=obj).count()


class CourseDetailSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.profile.full_name', read_only=True)
    instructor_email = serializers.EmailField(source='instructor.email', read_only=True)
    category = CategorySerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    enrollment_count = serializers.SerializerMethodField()
    enrollments_count = serializers.SerializerMethodField()  # Alias for template compatibility
    is_enrolled = serializers.SerializerMethodField()
    average_rating = serializers.SerializerMethodField()
    total_duration = serializers.SerializerMethodField()
    learning_outcomes = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'thumbnail', 'price',
            'is_free', 'status', 'level', 'instructor', 'instructor_name',
            'instructor_email', 'category', 'category_name', 'tags', 'modules', 'published_at',
            'created_at', 'updated_at', 'enrollment_count', 'enrollments_count', 'is_enrolled',
            'rejection_reason', 'average_rating', 'total_duration', 'learning_outcomes'
        ]

    def get_enrollment_count(self, obj):
        return obj.enrollments.filter(status='active').count()
    
    def get_enrollments_count(self, obj):
        # Alias for enrollment_count for template compatibility
        return obj.enrollments.filter(status='active').count()

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.enrollments.filter(user=request.user, status='active').exists()
        return False
    
    def get_average_rating(self, obj):
        from social.models import Review
        from django.db.models import Avg
        avg = Review.objects.filter(course=obj).aggregate(Avg('rating'))['rating__avg']
        return round(avg, 1) if avg else 0
    
    def get_total_duration(self, obj):
        total = 0
        for module in obj.modules.all():
            for lesson in module.lessons.all():
                total += lesson.duration_seconds or 0
        return total
    
    def get_learning_outcomes(self, obj):
        # Return empty list for now since field doesn't exist in model
        # This can be populated when the field is added to the Course model
        return []


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Course
        fields = [
            'id', 'slug', 'title', 'description', 'thumbnail', 'price', 'is_free',
            'level', 'category', 'tag_ids', 'status'
        ]
        read_only_fields = ['id', 'slug']

    def validate(self, attrs):
        if attrs.get('is_free'):
            attrs['price'] = 0
        return attrs

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        course = Course.objects.create(**validated_data)
        
        if tag_ids:
            for tag_id in tag_ids:
                CourseTag.objects.create(course=course, tag_id=tag_id)
        
        return course
    
    def to_representation(self, instance):
        """Ensure slug and id are always in response"""
        representation = super().to_representation(instance)
        # Explicitly add slug and id
        representation['id'] = instance.id
        representation['slug'] = instance.slug
        return representation

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if tag_ids is not None:
            CourseTag.objects.filter(course=instance).delete()
            for tag_id in tag_ids:
                CourseTag.objects.create(course=instance, tag_id=tag_id)
        
        return instance


class CourseCurriculumSerializer(serializers.ModelSerializer):
    modules = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'modules']

    def get_modules(self, course):
        modules = course.modules.order_by('position')
        return CurriculumModuleSerializer(
            modules,
            many=True,
            context=self.context
        ).data


# ===== COURSE VERSION SERIALIZER =====

class CourseVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseVersion
        fields = ['id', 'course', 'version_number', 'data', 'created_at']
        read_only_fields = ['created_at']