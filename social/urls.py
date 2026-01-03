from django.urls import path
from . import views

urlpatterns = [
    # Review endpoints
    path('courses/<int:course_id>/reviews/', views.course_reviews, name='course-reviews'),
    path('courses/<int:course_id>/reviews/submit/', views.submit_course_review, name='submit-review'),
    path('reviews/<int:review_id>/helpful/', views.mark_helpful, name='mark-review-helpful'),
    
    # Forum endpoints
    path('forums/', views.ForumListView.as_view(), name='forum-list'),
    path('forums/<int:forum_id>/threads/', views.ForumThreadListView.as_view(), name='forum-threads'),
    path('threads/<int:pk>/', views.ThreadDetailView.as_view(), name='thread-detail'),
    path('threads/<int:thread_id>/posts/', views.ThreadPostListView.as_view(), name='thread-posts'),
    path('posts/<int:post_id>/vote/', views.vote_on_post, name='vote-post'),
    
    # Learning Circle endpoints
    path('circles/', views.LearningCircleListCreateView.as_view(), name='circle-list-create'),
    path('circles/<int:pk>/', views.LearningCircleDetailView.as_view(), name='circle-detail'),
    path('circles/<int:circle_id>/join/', views.join_circle, name='join-circle'),
    path('circles/<int:circle_id>/leave/', views.leave_circle, name='leave-circle'),
    path('circles/my-circles/', views.my_circles, name='my-circles'),
    
    # Circle Chat
    path('circles/<int:circle_id>/messages/', views.circle_messages, name='circle-messages'),
    
    # Circle Goals
    path('circles/<int:circle_id>/goals/', views.circle_goals, name='circle-goals'),
    path('goals/<int:goal_id>/progress/', views.update_goal_progress, name='update-goal-progress'),
    
    # Circle Events
    path('circles/<int:circle_id>/events/', views.circle_events, name='circle-events'),
    
    # Circle Resources
    path('circles/<int:circle_id>/resources/', views.circle_resources, name='circle-resources'),
]
