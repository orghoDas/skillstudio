from rest_framework import serializers
from .models import Lesson

class LessonDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lesson
        fields = ['id', 'title', 'content_type', 'content_text', 'video_url', 'metadata', 'position', 'created_at']
        