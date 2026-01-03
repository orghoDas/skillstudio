from django.urls import path
from . import views

app_name = 'ai_recommender'

urlpatterns = [
    # Skills
    path('skills/', views.SkillListView.as_view(), name='skill-list'),
    path('skills/<slug:slug>/', views.SkillDetailView.as_view(), name='skill-detail'),
    
    # User Skills
    path('my-skills/', views.UserSkillListView.as_view(), name='user-skill-list'),
    path('my-skills/profile/', views.UserSkillProfileView.as_view(), name='user-skill-profile'),
    path('my-skills/update/', views.UpdateUserSkillView.as_view(), name='update-user-skills'),
    
    # User Interests
    path('interests/', views.UserInterestListView.as_view(), name='user-interest-list'),
    path('interests/<int:pk>/', views.UserInterestDetailView.as_view(), name='user-interest-detail'),
    
    # Recommendations
    path('recommendations/', views.RecommendationListView.as_view(), name='recommendation-list'),
    path('recommendations/generate/', views.GenerateRecommendationsView.as_view(), name='generate-recommendations'),
    path('recommendations/quick/', views.QuickRecommendationsView.as_view(), name='quick-recommendations'),
    path('recommendations/<int:pk>/', views.RecommendationDetailView.as_view(), name='recommendation-detail'),
    path('recommendations/<int:pk>/click/', views.ClickRecommendationView.as_view(), name='click-recommendation'),
    path('recommendations/<int:pk>/dismiss/', views.DismissRecommendationView.as_view(), name='dismiss-recommendation'),
    
    # Skill Gap Analysis
    path('skill-gaps/', views.SkillGapAnalysisListView.as_view(), name='skill-gap-list'),
    path('skill-gaps/create/', views.CreateSkillGapAnalysisView.as_view(), name='skill-gap-create'),
    path('skill-gaps/<int:pk>/', views.SkillGapAnalysisDetailView.as_view(), name='skill-gap-detail'),
    
    # Trending
    path('trending/skills/', views.TrendingSkillsView.as_view(), name='trending-skills'),
    path('trending/skills/update/', views.UpdateTrendingSkillsView.as_view(), name='update-trending-skills'),
    
    # Learning Paths
    path('learning-paths/', views.LearningPathListView.as_view(), name='learning-path-list'),
    path('learning-paths/enroll/', views.EnrollLearningPathView.as_view(), name='enroll-learning-path'),
    path('learning-paths/<slug:slug>/', views.LearningPathDetailView.as_view(), name='learning-path-detail'),
    path('my-learning-paths/', views.UserLearningPathListView.as_view(), name='user-learning-path-list'),
]
