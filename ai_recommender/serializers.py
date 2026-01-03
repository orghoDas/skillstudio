from rest_framework import serializers
from decimal import Decimal

from .models import (
    Skill, CourseSkill, UserSkill, UserInterest,
    Recommendation, SkillGapAnalysis, TrendingSkill,
    LearningPath, PathCourse, UserLearningPath
)
from courses.models import Course


class SkillSerializer(serializers.ModelSerializer):
    """Serializer for Skill model"""
    
    learner_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Skill
        fields = [
            'id', 'name', 'slug', 'category', 'description',
            'is_active', 'popularity_score', 'learner_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['slug', 'popularity_score', 'created_at', 'updated_at']


class CourseSkillSerializer(serializers.ModelSerializer):
    """Serializer for CourseSkill model"""
    
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    skill_category = serializers.CharField(source='skill.category', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    
    class Meta:
        model = CourseSkill
        fields = [
            'id', 'course', 'course_title', 'skill', 'skill_name', 
            'skill_category', 'weight', 'is_primary', 'added_by', 'created_at'
        ]
        read_only_fields = ['created_at']


class UserSkillSerializer(serializers.ModelSerializer):
    """Serializer for UserSkill model"""
    
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    skill_category = serializers.CharField(source='skill.category', read_only=True)
    
    class Meta:
        model = UserSkill
        fields = [
            'id', 'skill', 'skill_name', 'skill_category',
            'proficiency', 'source', 'first_learned_at', 'last_practiced_at'
        ]
        read_only_fields = ['first_learned_at', 'last_practiced_at']


class UserInterestSerializer(serializers.ModelSerializer):
    """Serializer for UserInterest model"""
    
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    
    class Meta:
        model = UserInterest
        fields = [
            'id', 'skill', 'skill_name', 'interest_level',
            'reason', 'target_proficiency', 'deadline',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RecommendationSerializer(serializers.ModelSerializer):
    """Serializer for Recommendation model"""
    
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    course_price = serializers.DecimalField(source='course.price', max_digits=12, decimal_places=2, read_only=True)
    course_level = serializers.CharField(source='course.level', read_only=True)
    instructor_name = serializers.SerializerMethodField()
    matched_skill_names = serializers.SerializerMethodField()
    
    class Meta:
        model = Recommendation
        fields = [
            'id', 'course', 'course_title', 'course_slug', 'course_price',
            'course_level', 'instructor_name', 'score', 'algorithm',
            'reason', 'matched_skill_names', 'status', 'clicked',
            'clicked_at', 'created_at', 'expires_at'
        ]
        read_only_fields = ['score', 'algorithm', 'reason', 'clicked', 'clicked_at', 'created_at', 'expires_at']
    
    def get_instructor_name(self, obj):
        if hasattr(obj.course, 'instructor') and hasattr(obj.course.instructor, 'profile'):
            return obj.course.instructor.profile.full_name or obj.course.instructor.email
        return obj.course.instructor.email
    
    def get_matched_skill_names(self, obj):
        return [skill.name for skill in obj.matched_skills.all()]


class SkillGapAnalysisSerializer(serializers.ModelSerializer):
    """Serializer for SkillGapAnalysis model"""
    
    target_skill_names = serializers.SerializerMethodField()
    
    class Meta:
        model = SkillGapAnalysis
        fields = [
            'id', 'target_role', 'target_skill_names', 'gap_score',
            'priority_skills', 'estimated_learning_hours', 'is_active',
            'progress', 'created_at', 'updated_at', 'last_analyzed_at'
        ]
        read_only_fields = ['gap_score', 'priority_skills', 'estimated_learning_hours', 'created_at', 'updated_at', 'last_analyzed_at']
    
    def get_target_skill_names(self, obj):
        return [skill.name for skill in obj.target_skills.all()]


class CreateSkillGapAnalysisSerializer(serializers.Serializer):
    """Serializer for creating skill gap analysis"""
    
    target_role = serializers.CharField(max_length=200)
    target_skills = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1
    )


class TrendingSkillSerializer(serializers.ModelSerializer):
    """Serializer for TrendingSkill model"""
    
    skill_name = serializers.CharField(source='skill.name', read_only=True)
    skill_category = serializers.CharField(source='skill.category', read_only=True)
    
    class Meta:
        model = TrendingSkill
        fields = [
            'id', 'skill', 'skill_name', 'skill_category',
            'period_start', 'period_end', 'period_type',
            'enrollment_count', 'search_count', 'completion_count',
            'trend_score', 'rank', 'rank_change', 'created_at'
        ]
        read_only_fields = ['created_at']


class PathCourseSerializer(serializers.ModelSerializer):
    """Serializer for PathCourse model"""
    
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True)
    course_level = serializers.CharField(source='course.level', read_only=True)
    
    class Meta:
        model = PathCourse
        fields = [
            'id', 'course', 'course_title', 'course_slug', 'course_level',
            'order', 'is_required'
        ]


class LearningPathSerializer(serializers.ModelSerializer):
    """Serializer for LearningPath model"""
    
    required_skill_names = serializers.SerializerMethodField()
    course_count = serializers.SerializerMethodField()
    completion_rate = serializers.FloatField(read_only=True)
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = LearningPath
        fields = [
            'id', 'title', 'slug', 'description', 'target_role',
            'difficulty_level', 'required_skill_names', 'course_count',
            'estimated_hours', 'estimated_weeks', 'created_by_name',
            'is_official', 'is_published', 'enrollment_count',
            'completion_count', 'completion_rate', 'avg_rating',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['slug', 'enrollment_count', 'completion_count', 'avg_rating', 'created_at', 'updated_at']
    
    def get_required_skill_names(self, obj):
        return [skill.name for skill in obj.required_skills.all()]
    
    def get_course_count(self, obj):
        return obj.courses.count()
    
    def get_created_by_name(self, obj):
        if obj.created_by and hasattr(obj.created_by, 'profile'):
            return obj.created_by.profile.full_name or obj.created_by.email
        return None


class LearningPathDetailSerializer(LearningPathSerializer):
    """Detailed serializer for LearningPath with courses"""
    
    courses = PathCourseSerializer(source='path_courses', many=True, read_only=True)
    
    class Meta(LearningPathSerializer.Meta):
        fields = LearningPathSerializer.Meta.fields + ['courses']


class UserLearningPathSerializer(serializers.ModelSerializer):
    """Serializer for UserLearningPath model"""
    
    path_title = serializers.CharField(source='learning_path.title', read_only=True)
    path_slug = serializers.CharField(source='learning_path.slug', read_only=True)
    total_courses = serializers.SerializerMethodField()
    completed_course_count = serializers.SerializerMethodField()
    
    class Meta:
        model = UserLearningPath
        fields = [
            'id', 'learning_path', 'path_title', 'path_slug',
            'progress', 'total_courses', 'completed_course_count',
            'started_at', 'completed_at', 'target_completion_date'
        ]
        read_only_fields = ['progress', 'started_at', 'completed_at']
    
    def get_total_courses(self, obj):
        return PathCourse.objects.filter(
            learning_path=obj.learning_path,
            is_required=True
        ).count()
    
    def get_completed_course_count(self, obj):
        return obj.completed_courses.count()


class EnrollLearningPathSerializer(serializers.Serializer):
    """Serializer for enrolling in learning path"""
    
    learning_path_id = serializers.IntegerField()
    target_completion_date = serializers.DateField(required=False, allow_null=True)


class CourseRecommendationSerializer(serializers.Serializer):
    """Simplified serializer for course recommendations"""
    
    id = serializers.IntegerField(source='course.id')
    title = serializers.CharField(source='course.title')
    slug = serializers.CharField(source='course.slug')
    price = serializers.DecimalField(source='course.price', max_digits=12, decimal_places=2)
    level = serializers.CharField(source='course.level')
    score = serializers.FloatField()
    reason = serializers.CharField()
    algorithm = serializers.CharField()


class UserSkillProfileSerializer(serializers.Serializer):
    """Complete user skill profile"""
    
    skills = UserSkillSerializer(many=True)
    interests = UserInterestSerializer(many=True)
    skill_gaps = SkillGapAnalysisSerializer(many=True)
    total_skills = serializers.IntegerField()
    avg_proficiency = serializers.FloatField()
