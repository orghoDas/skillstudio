"""
Payment URLs
URL routing for payment endpoints
"""

from django.urls import path
from payments import views, webhooks

app_name = 'payments'

urlpatterns = [
    # Payment history (courses are bought via POST /api/enrollments/enroll/;
    # there is intentionally no card "create payment" route — Decision D-01)
    path('', views.PaymentListView.as_view(), name='payment-list'),
    path('<int:payment_id>/', views.PaymentDetailView.as_view(), name='payment-detail'),
    path('<int:payment_id>/cancel/', views.PaymentCancelView.as_view(), name='payment-cancel'),
    
    # Refund endpoints
    path('refunds/', views.RefundListView.as_view(), name='refund-list'),
    path('refunds/request/', views.RefundRequestView.as_view(), name='refund-request'),
    path('refunds/<int:refund_id>/approve/', views.RefundApproveView.as_view(), name='refund-approve'),
    path('refunds/<int:refund_id>/reject/', views.RefundRejectView.as_view(), name='refund-reject'),
    
    # Payout endpoints
    path('payouts/', views.PayoutListView.as_view(), name='payout-list'),
    path('payouts/request/', views.PayoutRequestView.as_view(), name='payout-request'),
    path('payouts/balance/', views.PayoutBalanceView.as_view(), name='payout-balance'),
    path('payouts/<int:payout_id>/approve/', views.PayoutApproveView.as_view(), name='payout-approve'),
    
    # Coupon endpoints
    path('coupons/', views.CouponListView.as_view(), name='coupon-list'),
    path('coupons/create/', views.CouponCreateView.as_view(), name='coupon-create'),
    path('coupons/validate/', views.CouponValidateView.as_view(), name='coupon-validate'),
    path('coupons/<int:coupon_id>/deactivate/', views.CouponDeactivateView.as_view(), name='coupon-deactivate'),
    
    # Analytics endpoints
    path('stats/', views.PaymentStatsView.as_view(), name='payment-stats'),
    path('instructor/earnings/', views.InstructorEarningsView.as_view(), name='instructor-earnings'),
    
    # Webhook endpoint (Stripe, test mode). Rejects everything until the
    # verified top-up handler is implemented (AUDIT_REPORT.md PAY-04 / SEC-01).
    path('webhooks/stripe/', webhooks.StripeWebhookView.as_view(), name='webhook-stripe'),
]
