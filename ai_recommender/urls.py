from django.urls import path
from . import views

app_name = 'ai_recommender'

urlpatterns = [
    path('my/', views.UserRecommendationsView.as_view(), name='my-recommendations'),
    # Feature flag endpoint (admin only)
    path('feature-flag/', views.FeatureFlagView.as_view(), name='feature-flag'),
    # Frontend widget
    path('widget/', views.RecommendationWidgetView.as_view(), name='recommendation-widget'),
        path('widget-data/', views.recommendations_widget_data, name='recommendation-widget-data'), ]
