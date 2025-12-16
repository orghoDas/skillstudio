from rest_framework import serializers
from .models import LessonProgress

class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = ['lesson', 'is_completed']

        