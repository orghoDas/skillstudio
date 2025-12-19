from rest_framework import serializers
from .models import LessonProgress

class LessonProgressSerializer(serializers.ModelSerializer):
    lesson_title = serializers.CharField(source='lesson.title', read_only=True)

    class Meta:
        model = LessonProgress
        fields = ['id', 'lesson', 'lesson_title', 'is_completed', 'watch_time', 'started_at', 'completed_at']

        