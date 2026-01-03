from rest_framework import serializers
from django.contrib.auth import get_user_model
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
    class Meta:
        model = Lesson
        fields = [
            'module', 'title', 'content_type', 'content_text',
            'video_url', 'duration_seconds', 'metadata', 'position', 'is_free'
        ]

    def validate(self, attrs):
        content_type = attrs.get('content_type')
        
        if content_type == 'video' and not attrs.get('video_url'):
            raise serializers.ValidationError({
                'video_url': 'Video lessons must have a video URL.'
            })
        
        if content_type == 'text' and not attrs.get('content_text'):
            raise serializers.ValidationError({
                'content_text': 'Text lessons must have content.'
            })
        
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
    enrollment_count = serializers.SerializerMethodField()
    module_count = serializers.SerializerMethodField()
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'thumbnail', 'price',
            'is_free', 'status', 'level', 'instructor_name', 'instructor_email',
            'category_name', 'published_at', 'created_at', 'enrollment_count',
            'module_count', 'lesson_count'
        ]

    def get_enrollment_count(self, obj):
        return obj.enrollments.filter(status='active').count()

    def get_module_count(self, obj):
        return obj.modules.count()

    def get_lesson_count(self, obj):
        return Lesson.objects.filter(module__course=obj).count()


class CourseDetailSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.profile.full_name', read_only=True)
    instructor_email = serializers.EmailField(source='instructor.email', read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    modules = ModuleSerializer(many=True, read_only=True)
    enrollment_count = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'thumbnail', 'price',
            'is_free', 'status', 'level', 'instructor', 'instructor_name',
            'instructor_email', 'category', 'tags', 'modules', 'published_at',
            'created_at', 'updated_at', 'enrollment_count', 'is_enrolled',
            'rejection_reason'
        ]

    def get_enrollment_count(self, obj):
        return obj.enrollments.filter(status='active').count()

    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.enrollments.filter(user=request.user, status='active').exists()
        return False


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Course
        fields = [
            'title', 'description', 'thumbnail', 'price', 'is_free',
            'level', 'category', 'tag_ids', 'status'
        ]

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