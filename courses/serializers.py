from rest_framework import serializers
from .models import Course, Lesson, Module

class LessonDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content_type', 'content_text', 'video_url', 'metadata', 'position', 'created_at']


class LessonListSerializer(serializers.ModelSerializer):
    is_completed = serializers.BooleanField()
    is_locked = serializers.BooleanField()

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'position', 'is_free', 'is_completed', 'is_locked']


class CurriculumLessonSerializer(serializers.ModelSerializer):
    is_completed = serializers.SerializerMethodField()
    is_locked = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ['id', 'title', 'position', 'is_free', 'is_completed', 'is_locked']

    def get_is_completed(self, lesson):
        return lesson.id in self.context.get('completed_ids', set())

    def get_is_locked(self, lesson):
        if lesson.is_free:
            return False
        return lesson.id in self.context.get('locked_ids', set())


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