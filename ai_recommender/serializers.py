from rest_framework import serializers
from .models import Recommendation
from courses.models import Course


class CourseMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ('id', 'title', 'slug', 'thumbnail')


class RecommendationSerializer(serializers.ModelSerializer):
    course = CourseMinimalSerializer()

    class Meta:
        model = Recommendation
        fields = ('id', 'course', 'score', 'reason', 'status', 'created_at')
