from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.db.models import Avg, Count
from django.db import transaction
from django.shortcuts import get_object_or_404

from . import services
from .models import (
    Skill, CourseSkill, UserSkill, UserInterest,
    Recommendation, SkillGapAnalysis, TrendingSkill,
    LearningPath, UserLearningPath
)
from .serializers import (
    SkillSerializer, CourseSkillSerializer, UserSkillSerializer,
    UserInterestSerializer, RecommendationSerializer,
    SkillGapAnalysisSerializer, CreateSkillGapAnalysisSerializer,
    TrendingSkillSerializer, LearningPathSerializer,
    LearningPathDetailSerializer, UserLearningPathSerializer,
    EnrollLearningPathSerializer, CourseRecommendationSerializer,
    UserSkillProfileSerializer
)


# ===========================
# Skill Views
# ===========================

class SkillListView(generics.ListAPIView):
    """List all active skills"""
    
    queryset = Skill.objects.filter(is_active=True).order_by('-popularity_score', 'name')
    serializer_class = SkillSerializer
    permission_classes = []
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Search by name
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        return queryset


class SkillDetailView(generics.RetrieveAPIView):
    """Get skill details"""
    
    queryset = Skill.objects.filter(is_active=True)
    serializer_class = SkillSerializer
    lookup_field = 'slug'
    permission_classes = []


# ===========================
# User Skill Views
# ===========================

class UserSkillListView(generics.ListAPIView):
    """List user's skills"""
    
    serializer_class = UserSkillSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserSkill.objects.filter(
            user=self.request.user
        ).select_related('skill').order_by('-proficiency')


class UserSkillProfileView(APIView):
    """Get complete user skill profile"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        skills = UserSkill.objects.filter(user=user).select_related('skill')
        interests = UserInterest.objects.filter(user=user).select_related('skill')
        skill_gaps = SkillGapAnalysis.objects.filter(user=user, is_active=True).prefetch_related('target_skills')
        
        # Calculate stats
        total_skills = skills.count()
        avg_proficiency = skills.aggregate(avg=Avg('proficiency'))['avg'] or 0.0
        
        serializer = UserSkillProfileSerializer({
            'skills': skills,
            'interests': interests,
            'skill_gaps': skill_gaps,
            'total_skills': total_skills,
            'avg_proficiency': avg_proficiency,
        })
        
        return Response(serializer.data)


class UpdateUserSkillView(APIView):
    """Update user skill proficiency"""
    
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        # Trigger skill update based on completed courses
        updated_skills = services.update_user_skills(request.user)
        
        serializer = UserSkillSerializer(updated_skills, many=True)
        
        return Response({
            'message': f'Updated {len(updated_skills)} skills',
            'skills': serializer.data
        })


# ===========================
# User Interest Views
# ===========================

class UserInterestListView(generics.ListCreateAPIView):
    """List and create user interests"""
    
    serializer_class = UserInterestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserInterest.objects.filter(
            user=self.request.user
        ).select_related('skill').order_by('-interest_level')
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class UserInterestDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete a user interest"""
    
    serializer_class = UserInterestSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserInterest.objects.filter(user=self.request.user)


# ===========================
# Recommendation Views
# ===========================

class RecommendationListView(generics.ListAPIView):
    """List active recommendations for user"""
    
    serializer_class = RecommendationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Recommendation.objects.filter(
            user=self.request.user,
            status='active'
        ).select_related('course', 'course__instructor').prefetch_related('matched_skills').order_by('-score')


class GenerateRecommendationsView(APIView):
    """Generate fresh recommendations"""
    
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        algorithm = request.data.get('algorithm', 'hybrid')
        limit = int(request.data.get('limit', 10))
        
        # Generate recommendations
        recommendations = services.generate_recommendations(
            user=request.user,
            algorithm=algorithm,
            limit=limit,
            save=True
        )
        
        serializer = RecommendationSerializer(recommendations, many=True)
        
        return Response({
            'message': f'Generated {len(recommendations)} recommendations using {algorithm} algorithm',
            'recommendations': serializer.data
        }, status=status.HTTP_201_CREATED)


class RecommendationDetailView(generics.RetrieveAPIView):
    """Get recommendation details"""
    
    serializer_class = RecommendationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Recommendation.objects.filter(user=self.request.user)


class ClickRecommendationView(APIView):
    """Track when user clicks a recommendation"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        recommendation = get_object_or_404(
            Recommendation,
            pk=pk,
            user=request.user
        )
        
        recommendation.mark_clicked()
        
        return Response({
            'message': 'Recommendation click tracked',
            'clicked_at': recommendation.clicked_at
        })


class DismissRecommendationView(APIView):
    """Dismiss a recommendation"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, pk):
        recommendation = get_object_or_404(
            Recommendation,
            pk=pk,
            user=request.user
        )
        
        recommendation.dismiss()
        
        return Response({
            'message': 'Recommendation dismissed'
        })


# ===========================
# Skill Gap Analysis Views
# ===========================

class SkillGapAnalysisListView(generics.ListAPIView):
    """List user's skill gap analyses"""
    
    serializer_class = SkillGapAnalysisSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SkillGapAnalysis.objects.filter(
            user=self.request.user
        ).prefetch_related('target_skills').order_by('-created_at')


class CreateSkillGapAnalysisView(APIView):
    """Create a new skill gap analysis"""
    
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        serializer = CreateSkillGapAnalysisSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        # Create analysis
        analysis = services.create_skill_gap_analysis(
            user=request.user,
            target_role=data['target_role'],
            target_skill_names=data['target_skills']
        )
        
        response_serializer = SkillGapAnalysisSerializer(analysis)
        
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


class SkillGapAnalysisDetailView(generics.RetrieveDestroyAPIView):
    """Get or delete skill gap analysis"""
    
    serializer_class = SkillGapAnalysisSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return SkillGapAnalysis.objects.filter(user=self.request.user)


# ===========================
# Trending Skills Views
# ===========================

class TrendingSkillsView(generics.ListAPIView):
    """Get trending skills"""
    
    serializer_class = TrendingSkillSerializer
    permission_classes = []
    
    def get_queryset(self):
        period_type = self.request.query_params.get('period', 'weekly')
        
        trending = services.get_trending_skills(period_type=period_type, limit=20)
        
        return trending


class UpdateTrendingSkillsView(APIView):
    """Update trending skills (admin only)"""
    
    permission_classes = [IsAdminUser]
    
    @transaction.atomic
    def post(self, request):
        period_type = request.data.get('period_type', 'weekly')
        
        trending = services.update_trending_skills(period_type=period_type)
        
        serializer = TrendingSkillSerializer(trending[:20], many=True)
        
        return Response({
            'message': f'Updated {len(trending)} trending skills',
            'trending_skills': serializer.data
        })


# ===========================
# Learning Path Views
# ===========================

class LearningPathListView(generics.ListAPIView):
    """List published learning paths"""
    
    serializer_class = LearningPathSerializer
    permission_classes = []
    
    def get_queryset(self):
        queryset = LearningPath.objects.filter(
            is_published=True
        ).prefetch_related('required_skills').order_by('-is_official', '-enrollment_count')
        
        # Filter by difficulty
        difficulty = self.request.query_params.get('difficulty')
        if difficulty:
            queryset = queryset.filter(difficulty_level=difficulty)
        
        # Search
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(title__icontains=search)
        
        return queryset


class LearningPathDetailView(generics.RetrieveAPIView):
    """Get learning path details with courses"""
    
    queryset = LearningPath.objects.filter(is_published=True)
    serializer_class = LearningPathDetailSerializer
    lookup_field = 'slug'
    permission_classes = []


class UserLearningPathListView(generics.ListAPIView):
    """List user's enrolled learning paths"""
    
    serializer_class = UserLearningPathSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return UserLearningPath.objects.filter(
            user=self.request.user
        ).select_related('learning_path').order_by('-started_at')


class EnrollLearningPathView(APIView):
    """Enroll in a learning path"""
    
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        serializer = EnrollLearningPathSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        data = serializer.validated_data
        
        enrollment = services.enroll_in_learning_path(
            user=request.user,
            learning_path_id=data['learning_path_id'],
            target_date=data.get('target_completion_date')
        )
        
        response_serializer = UserLearningPathSerializer(enrollment)
        
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )


# ===========================
# Quick Recommendations (Legacy)
# ===========================

class QuickRecommendationsView(APIView):
    """Get quick course recommendations without saving (legacy endpoint)"""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        algorithm = request.query_params.get('algorithm', 'hybrid')
        limit = int(request.query_params.get('limit', 10))
        
        # Generate without saving
        recommendations = services.generate_recommendations(
            user=request.user,
            algorithm=algorithm,
            limit=limit,
            save=False
        )
        
        serializer = CourseRecommendationSerializer(recommendations, many=True)
        
        return Response({
            'recommended_courses': serializer.data
        })
