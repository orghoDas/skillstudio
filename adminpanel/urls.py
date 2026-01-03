from django.urls import path
from adminpanel.views import (
    # Dashboard
    AdminDashboardView, PlatformStatsView,
    # User Management
    UserManagementListView, UserDetailView, ApproveInstructorView, 
    SuspendUserView, ActivateUserView, DeleteUserView,
    # Course Moderation
    PendingCoursesView, ApproveCourseView, RejectCourseView, DeleteCourseView,
    # Content Moderation
    ContentModerationQueueView, ModerateContentView, 
    FlaggedReviewsView, RemoveReviewView, ApproveReviewView,
    # Payment & Revenue
    PaymentListView, RevenueStatsView, RefundPaymentView, 
    PayoutListView, ApprovePayoutView,
    # Settings & Alerts
    PlatformSettingsView, SystemAlertListView, SystemAlertDetailView,
    # Activity Log
    AdminActivityLogView,
)

app_name = 'adminpanel'

urlpatterns = [
    # Dashboard
    path('dashboard/', AdminDashboardView.as_view(), name='admin-dashboard'),
    path('stats/', PlatformStatsView.as_view(), name='platform-stats'),
    
    # User Management
    path('users/', UserManagementListView.as_view(), name='user-list'),
    path('users/<int:user_id>/', UserDetailView.as_view(), name='user-detail'),
    path('users/<int:user_id>/approve-instructor/', ApproveInstructorView.as_view(), name='approve-instructor'),
    path('users/<int:user_id>/suspend/', SuspendUserView.as_view(), name='suspend-user'),
    path('users/<int:user_id>/activate/', ActivateUserView.as_view(), name='activate-user'),
    path('users/<int:user_id>/delete/', DeleteUserView.as_view(), name='delete-user'),
    
    # Course Moderation
    path('courses/pending/', PendingCoursesView.as_view(), name='pending-courses'),
    path('courses/<int:course_id>/approve/', ApproveCourseView.as_view(), name='approve-course'),
    path('courses/<int:course_id>/reject/', RejectCourseView.as_view(), name='reject-course'),
    path('courses/<int:course_id>/delete/', DeleteCourseView.as_view(), name='delete-course'),
    
    # Content Moderation
    path('moderation/queue/', ContentModerationQueueView.as_view(), name='moderation-queue'),
    path('moderation/<int:content_id>/', ModerateContentView.as_view(), name='moderate-content'),
    path('reviews/flagged/', FlaggedReviewsView.as_view(), name='flagged-reviews'),
    path('reviews/<int:review_id>/remove/', RemoveReviewView.as_view(), name='remove-review'),
    path('reviews/<int:review_id>/approve/', ApproveReviewView.as_view(), name='approve-review'),
    
    # Payment & Revenue Management
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('revenue/', RevenueStatsView.as_view(), name='revenue-stats'),
    path('payments/<int:payment_id>/refund/', RefundPaymentView.as_view(), name='refund-payment'),
    path('payouts/', PayoutListView.as_view(), name='payout-list'),
    path('payouts/<int:payout_id>/approve/', ApprovePayoutView.as_view(), name='approve-payout'),
    
    # Platform Settings
    path('settings/', PlatformSettingsView.as_view(), name='platform-settings'),
    
    # System Alerts
    path('alerts/', SystemAlertListView.as_view(), name='system-alerts'),
    path('alerts/<int:alert_id>/', SystemAlertDetailView.as_view(), name='alert-detail'),
    
    # Activity Log
    path('activity-log/', AdminActivityLogView.as_view(), name='activity-log'),
]

