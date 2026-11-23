from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from .models import StudentProfile, StudentNote, StudentBookmark, Wallet, WalletTransaction
from courses.models import Lesson
from courses.policies import visible_catalog_courses

User = get_user_model()


class StudentProfileSerializer(serializers.ModelSerializer):
    """Serializer for student profile."""
    
    weekly_study_hours = serializers.IntegerField(min_value=0, max_value=168, required=False)
    interests = serializers.ListField(child=serializers.CharField(), required=False)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = StudentProfile
        fields = [
            'id',
            'user',
            'user_email',
            'preferred_learning_style',
            'learning_goals',
            'interests',
            'weekly_study_hours',
            'preferred_study_time',
            'total_courses_enrolled',
            'total_courses_completed',
            'total_certificates_earned',
            'total_watch_time',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'total_courses_enrolled',
            'total_courses_completed',
            'total_certificates_earned',
            'total_watch_time',
            'created_at',
            'updated_at',
        ]


class StudentNoteSerializer(serializers.ModelSerializer):
    """Serializer for student notes."""
    
    timestamp = serializers.IntegerField(min_value=0, max_value=2**31 - 1, required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    course_id = serializers.IntegerField(source='lesson.module.course.id', read_only=True)
    course_title = serializers.CharField(source='lesson.module.course.title', read_only=True)
    
    class Meta:
        model = StudentNote
        fields = [
            'id',
            'user',
            'lesson',
            'lesson_title',
            'course_id',
            'course_title',
            'content',
            'timestamp',
            'is_pinned',
            'tags',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']


class StudentNoteUpdateSerializer(StudentNoteSerializer):
    class Meta(StudentNoteSerializer.Meta):
        read_only_fields = [*StudentNoteSerializer.Meta.read_only_fields, 'lesson']


class StudentNoteListSerializer(serializers.ModelSerializer):
    """Simplified serializer for note lists."""
    
    course_slug = serializers.SlugField(source='lesson.module.course.slug', read_only=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)
    
    class Meta:
        model = StudentNote
        fields = [
            'id',
            'lesson',
            'lesson_title',
            'course_slug',
            'content',
            'timestamp',
            'is_pinned',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class StudentBookmarkSerializer(serializers.ModelSerializer):
    """Serializer for student bookmarks."""
    
    course_slug = serializers.SerializerMethodField()
    course_title = serializers.CharField(source='course.title', read_only=True, allow_null=True)
    lesson_title = serializers.CharField(source='lesson.title', read_only=True, allow_null=True)
    
    class Meta:
        model = StudentBookmark
        fields = [
            'id',
            'user',
            'course',
            'course_title',
            'course_slug',
            'lesson',
            'lesson_title',
            'note',
            'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']

    def get_course_slug(self, obj) -> str:
        return obj.course.slug if obj.course_id else obj.lesson.module.course.slug

    def get_fields(self):
        fields = super().get_fields()
        user = getattr(self.context.get('request'), 'user', None)
        visible_courses = visible_catalog_courses(user)
        fields['course'].queryset = visible_courses
        fields['lesson'].queryset = Lesson.objects.filter(module__course__in=visible_courses)
        fields['course'].error_messages['does_not_exist'] = 'Course not found.'
        fields['lesson'].error_messages['does_not_exist'] = 'Lesson not found.'
        return fields

    def validate(self, data):
        """Ensure either course or lesson is provided, but not both."""
        course = data.get('course', self.instance.course if self.instance else None)
        lesson = data.get('lesson', self.instance.lesson if self.instance else None)
        
        if not course and not lesson:
            raise serializers.ValidationError(
                "Either course or lesson must be provided."
            )
        
        if course and lesson:
            raise serializers.ValidationError(
                "Cannot bookmark both course and lesson simultaneously."
            )
        
        return data


class StudentDashboardSerializer(serializers.Serializer):
    """Serializer for student dashboard data."""
    
    course_id = serializers.IntegerField()
    course_title = serializers.CharField()
    status = serializers.CharField()
    is_completed = serializers.BooleanField()
    progress_percentage = serializers.FloatField()
    completed_lessons = serializers.IntegerField()
    total_lessons = serializers.IntegerField()
    has_certificate = serializers.BooleanField()
    resume_lesson_id = serializers.IntegerField(allow_null=True)
    last_activity = serializers.DateTimeField(allow_null=True)
    resume_context = serializers.DictField(allow_null=True)
    primary_action = serializers.CharField()
    action_target = serializers.IntegerField(allow_null=True)


class StudentActivityFeedSerializer(serializers.Serializer):
    """Serializer for activity feed items."""
    
    type = serializers.CharField()
    course_id = serializers.IntegerField()
    course_title = serializers.CharField()
    lesson_id = serializers.IntegerField(required=False, allow_null=True)
    lesson_title = serializers.CharField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField()


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Serializer for wallet transactions."""
    
    class Meta:
        model = WalletTransaction
        fields = ['id', 'transaction_type', 'amount', 'description', 'balance_after', 'created_at']
        read_only_fields = ['id', 'created_at']


class WalletSerializer(serializers.ModelSerializer):
    """Serializer for wallet."""
    
    recent_transactions = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = ['id', 'balance', 'created_at', 'updated_at', 'recent_transactions']
        read_only_fields = ['id', 'balance', 'created_at', 'updated_at']
    
    @extend_schema_field(WalletTransactionSerializer(many=True))
    def get_recent_transactions(self, obj):
        """Get recent transactions (last 10)."""
        transactions = obj.transactions.all()[:10]
        return WalletTransactionSerializer(transactions, many=True).data
