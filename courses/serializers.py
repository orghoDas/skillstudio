from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Max
from accounts.utils import public_instructor_name
from enrollments.services import get_access_enrollment, lesson_lock_state, ordered_course_lessons
from .policies import can_access_course_content, can_manage_course
from .video import parse_video_url
from .models import (
    Course, Lesson, Module, Category, Tag, CourseTag,
    LessonResource
)

User = get_user_model()


# ===== CATEGORY & TAG SERIALIZERS =====

class CategorySerializer(serializers.ModelSerializer):
    course_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'course_count']
        read_only_fields = ['slug']

    def get_course_count(self, obj) -> int:
        if hasattr(obj, 'course_count'):
            return obj.course_count
        return obj.courses.filter(status='published').count()

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except IntegrityError as exc:
            if Category.objects.filter(name=validated_data['name']).exists():
                raise serializers.ValidationError({'name': ['A category with this name already exists.']}) from exc
            raise


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
            'id', 'id', 'module', 'title', 'content_type', 'content_text',
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
    position = serializers.IntegerField(required=False, min_value=0, max_value=2**31 - 1)
    is_free = serializers.BooleanField(required=False, default=False)
    
    class Meta:
        model = Lesson
        fields = [
            'id', 'module', 'title', 'content_type', 'content_text',
            'video_url', 'duration_seconds', 'metadata', 'position', 'is_free'
        ]
        # The destination module can come from the URL. Check positions when
        # saving, after the view has resolved the module and locked the course.
        validators = []

    def validate_module(self, value):
        # SEC-05: on update a lesson may only move between modules of its own
        # course (ownership was checked on that course); never into another one.
        if (
            self.instance is not None
            and value is not None
            and value.course_id != self.instance.module.course_id
        ):
            raise serializers.ValidationError("A lesson can't be moved to another course.")
        return value

    def validate_video_url(self, value):
        # Only sources the learn page can play *and observe* are accepted, so
        # watch time can be tracked and video lessons can be completed (LRN-02).
        if value and parse_video_url(value) is None:
            raise serializers.ValidationError(
                "Use a YouTube or Vimeo link, or a direct link to a video file (.mp4, .webm, .ogg)."
            )
        return value

    def create(self, validated_data):
        self._set_position(validated_data, validated_data['module'])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        module = validated_data.get('module', instance.module)
        if 'position' in validated_data or module.pk != instance.module_id:
            self._set_position(validated_data, module)
        return super().update(instance, validated_data)

    def _set_position(self, validated_data, module):
        siblings = module.lessons.all()
        if self.instance is not None:
            siblings = siblings.exclude(pk=self.instance.pk)
        if 'position' in validated_data:
            if siblings.filter(position=validated_data['position']).exists():
                raise serializers.ValidationError({'position': 'This position is already in use in this module.'})
            return

        last = siblings.aggregate(last=Max('position', default=-1))['last']
        if last == self.fields['position'].max_value:
            raise serializers.ValidationError({'position': 'Specify an unused position in this module.'})
        validated_data['position'] = last + 1


class LessonDataSerializer(serializers.ModelSerializer):
    """Full lesson content for someone allowed to study it (LessonDetailView)."""
    resources = LessonResourceSerializer(many=True, read_only=True)
    module_title = serializers.CharField(source='module.title', read_only=True)
    video = serializers.SerializerMethodField(
        help_text="Player descriptor parsed from video_url: {provider: youtube|vimeo|file, id|url} or null."
    )

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'content_type', 'content_text', 'video_url', 'video',
            'metadata', 'position', 'created_at', 'duration_seconds',
            'is_free', 'resources', 'module_title'
        ]

    def get_video(self, obj) -> dict | None:
        return parse_video_url(obj.video_url)


class CurriculumLessonSerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'position', 'is_free', 'content_type',
            'duration_seconds', 'is_completed', 'is_locked'
        ]

    def get_is_completed(self, lesson) -> bool:
        return lesson.id in self.context.get('completed_ids', set())

    def get_is_locked(self, lesson) -> bool:
        return lesson.id in self.context.get('locked_ids', set())


# ===== MODULE SERIALIZERS =====

class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'position', 'created_at', 'lessons', 'lesson_count']
        read_only_fields = ['created_at']

    def get_lesson_count(self, obj) -> int:
        return obj.lessons.count()


class ModuleCreateUpdateSerializer(serializers.ModelSerializer):
    """Create/update a module.

    ``course`` is only meaningful on create; the views check that the caller
    can manage it. On update it can never change (SEC-05): ownership is checked on
    the module's *current* course, so allowing a new course would let an
    instructor inject their module into someone else's course.
    """
    course = serializers.PrimaryKeyRelatedField(queryset=Course.objects.all(), required=False)

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'position']

    def validate_course(self, value):
        if self.instance is not None and value is not None and value.pk != self.instance.course_id:
            raise serializers.ValidationError("A module can't be moved to another course.")
        return value


class CurriculumModuleSerializer(serializers.ModelSerializer):
    lessons = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'title', 'position', 'lessons']

    @extend_schema_field(CurriculumLessonSerializer(many=True))
    def get_lessons(self, module):
        lessons = module.lessons.all()
        return CurriculumLessonSerializer(
            lessons,
            many=True,
            context=self.context
        ).data


class CourseDetailLessonSerializer(serializers.ModelSerializer):
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = [
            'id', 'title', 'position', 'is_free', 'content_type',
            'duration_seconds', 'is_locked'
        ]

    def get_is_locked(self, lesson) -> bool:
        module = lesson.module
        locks_by_course = self.context.setdefault('lesson_locks_by_course', {})
        if module.course_id not in locks_by_course:
            course = module.course
            user = getattr(self.context.get('request'), 'user', None)
            enrollment = None if can_manage_course(user, course) else get_access_enrollment(user, course)
            if enrollment:
                locks = lesson_lock_state(enrollment, ordered_course_lessons(course))
            elif can_access_course_content(user, course):
                locks = {}
            else:
                # A visible paid course still offers its free previews.
                locks = {item.pk: not item.is_free for item in ordered_course_lessons(course)}
            locks_by_course[module.course_id] = locks
        return locks_by_course[module.course_id].get(lesson.pk, False)


class CatalogLessonSummarySerializer(CourseDetailLessonSerializer):
    class Meta:
        model = Lesson
        fields = [
            'id', 'module', 'title', 'position', 'is_free', 'content_type',
            'duration_seconds', 'is_locked'
        ]


class CourseDetailModuleSerializer(serializers.ModelSerializer):
    lessons = CourseDetailLessonSerializer(many=True, read_only=True)
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'title', 'position', 'created_at', 'lessons', 'lesson_count']
        read_only_fields = ['created_at']

    def get_lesson_count(self, obj) -> int:
        return obj.lessons.count()


class CatalogModuleSerializer(serializers.ModelSerializer):
    lessons = CatalogLessonSummarySerializer(many=True, read_only=True)
    lesson_count = serializers.SerializerMethodField()

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'position', 'created_at', 'lessons', 'lesson_count']
        read_only_fields = ['created_at']

    def get_lesson_count(self, obj) -> int:
        return obj.lessons.count()


# ===== COURSE SERIALIZERS =====

class CourseListSerializer(serializers.ModelSerializer):
    rejection_reason = serializers.CharField(read_only=True)
    reviewed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    instructor_name = serializers.SerializerMethodField()
    instructor_id = serializers.IntegerField(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    enrollments_count = serializers.IntegerField(read_only=True)
    module_count = serializers.IntegerField(read_only=True)
    lesson_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'thumbnail', 'price',
            'is_free', 'status', 'level', 'instructor_id', 'instructor_name',
            'category_name', 'published_at', 'created_at', 'enrollments_count',
            'module_count', 'lesson_count', 'rejection_reason', 'reviewed_at'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = getattr(self.context.get('request'), 'user', None)
        if not data['rejection_reason'] or not can_manage_course(user, instance):
            data.pop('rejection_reason', None)
            data.pop('reviewed_at', None)
        return data

    def get_instructor_name(self, obj) -> str:
        return public_instructor_name(obj.instructor)


class CourseDetailSerializer(serializers.ModelSerializer):
    rejection_reason = serializers.CharField(read_only=True)
    reviewed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    instructor_name = serializers.SerializerMethodField()
    instructor_id = serializers.IntegerField(read_only=True)
    category = CategorySerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    modules = CourseDetailModuleSerializer(many=True, read_only=True)
    enrollment_count = serializers.IntegerField(source='enrollments_count', read_only=True)
    enrollments_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    total_duration = serializers.SerializerMethodField()
    version_number = serializers.IntegerField(source='current_version.version_number', read_only=True, default=None)

    class Meta:
        model = Course
        fields = [
            'id', 'title', 'slug', 'description', 'thumbnail', 'price',
            'is_free', 'status', 'level', 'instructor', 'instructor_id', 'instructor_name',
            'category', 'category_name', 'tags', 'modules', 'published_at',
            'created_at', 'updated_at', 'enrollment_count', 'enrollments_count', 'is_enrolled',
            'rejection_reason', 'reviewed_at', 'total_duration', 'revision_of', 'version_number'
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        user = getattr(self.context.get('request'), 'user', None)
        if not can_manage_course(user, instance):
            data.pop('rejection_reason', None)
            data.pop('reviewed_at', None)
        return data

    def get_is_enrolled(self, obj) -> bool:
        return self.context['is_enrolled']
    
    def get_total_duration(self, obj) -> int:
        total = 0
        for module in obj.modules.all():
            for lesson in module.lessons.all():
                total += lesson.duration_seconds or 0
        return total
    
    def get_instructor_name(self, obj) -> str:
        return public_instructor_name(obj.instructor)


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=2**63 - 1),
        write_only=True,
        required=False
    )

    class Meta:
        model = Course
        fields = [
            'id', 'slug', 'title', 'description', 'thumbnail', 'price', 'is_free',
            'level', 'category', 'tag_ids', 'status'
        ]
        read_only_fields = ['id', 'slug', 'status']

    def validate(self, attrs):
        price = attrs.get('price', getattr(self.instance, 'price', 0))
        if 'price' not in attrs and attrs.get('is_free') is True:
            price = attrs['price'] = 0

        is_free = attrs.get('is_free', getattr(self.instance, 'is_free', price == 0))
        if is_free and price != 0:
            raise serializers.ValidationError({'price': 'Free courses must have a zero price.'})
        if not is_free and price <= 0:
            raise serializers.ValidationError({'price': 'Paid courses must have a positive price.'})
        if self.instance is None:
            attrs['is_free'] = is_free
        return attrs

    def validate_tag_ids(self, value):
        ids = list(dict.fromkeys(value))
        self._check_tags(ids)
        return ids

    @staticmethod
    def _check_tags(tag_ids, *, lock=False):
        if not tag_ids:
            return
        tags = Tag.objects.filter(pk__in=tag_ids).order_by('pk')
        if lock:
            tags = tags.select_for_update()
        missing = set(tag_ids).difference(tags.values_list('pk', flat=True))
        if missing:
            raise serializers.ValidationError({'tag_ids': f"Unknown tag IDs: {', '.join(map(str, sorted(missing)))}."})

    @staticmethod
    def _add_tags(course, tag_ids):
        CourseTag.objects.bulk_create([CourseTag(course=course, tag_id=tag_id) for tag_id in tag_ids])

    @transaction.atomic
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        self._check_tags(tag_ids, lock=True)
        course = super().create(validated_data)
        self._add_tags(course, tag_ids)
        return course
    
    def to_representation(self, instance):
        """Ensure slug and id are always in response"""
        representation = super().to_representation(instance)
        # Explicitly add slug and id
        representation['id'] = instance.id
        representation['slug'] = instance.slug
        return representation

    @transaction.atomic
    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        self._check_tags(tag_ids, lock=True)
        course = super().update(instance, validated_data)

        if tag_ids is not None:
            CourseTag.objects.filter(course=course).delete()
            self._add_tags(course, tag_ids)
        return course


class CourseCurriculumSerializer(serializers.ModelSerializer):
    modules = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ['id', 'title', 'modules']

    @extend_schema_field(CurriculumModuleSerializer(many=True))
    def get_modules(self, course):
        modules = course.modules.all()
        return CurriculumModuleSerializer(
            modules,
            many=True,
            context=self.context
        ).data
