"""
Payment Serializers
Serializers for payment-related models
"""

from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone

from payments.models import (
    Payment, Payout, Refund, Coupon, CouponRedemption,
    PaymentGatewayConfig, PaymentWebhookLog, PaymentDispute
)
from accounts.models import User
from courses.models import Course
# from events.models import Event  # Removed - events app disabled


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    instructor_email = serializers.EmailField(source='instructor.email', read_only=True, allow_null=True)
    course_title = serializers.CharField(source='course.title', read_only=True, allow_null=True)
    # event_title = serializers.CharField(source='event.title', read_only=True, allow_null=True)  # Removed
    
    class Meta:
        model = Payment
        fields = [
            'id', 'user', 'user_email', 'instructor', 'instructor_email',
            'course', 'course_title',  # 'event', 'event_title',  # Removed
            'amount', 'original_amount', 'discount_amount', 'currency',
            'platform_fee', 'instructor_earnings',
            'payment_method', 'provider', 'provider_id',
            'coupon', 'status', 'failure_reason',
            'billing_email', 'billing_address',
            'metadata', 'ip_address',
            'created_at', 'updated_at', 'completed_at',
            'is_successful', 'can_be_refunded'
        ]
        read_only_fields = [
            'id', 'instructor', 'platform_fee', 'instructor_earnings',
            'provider_id', 'status', 'created_at', 'updated_at',
            'completed_at', 'is_successful', 'can_be_refunded'
        ]


class PaymentCreateSerializer(serializers.Serializer):
    """Serializer for creating payments"""
    
    course_id = serializers.IntegerField(required=True)  # Made required since events removed
    # event_id = serializers.IntegerField(required=False, allow_null=True)  # Removed
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES, default='stripe')
    coupon_code = serializers.CharField(max_length=64, required=False, allow_blank=True)
    billing_email = serializers.EmailField(required=False)
    billing_address = serializers.JSONField(required=False)
    
    # Removed validation - only courses now
    # def validate(self, data):
    #     if not data.get('course_id') and not data.get('event_id'):
    #         raise serializers.ValidationError("Either course_id or event_id must be provided")
    #     
    #     if data.get('course_id') and data.get('event_id'):
    #         raise serializers.ValidationError("Cannot purchase both course and event in single payment")
    #     
    #     return data


class PayoutSerializer(serializers.ModelSerializer):
    """Serializer for Payout model"""
    
    instructor_email = serializers.EmailField(source='instructor.email', read_only=True)
    instructor_name = serializers.SerializerMethodField()
    payment_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Payout
        fields = [
            'id', 'instructor', 'instructor_email', 'instructor_name',
            'amount', 'currency', 'payment_count',
            'status', 'payout_method', 'account_details',
            'transaction_id', 'provider_details',
            'failure_reason', 'admin_notes',
            'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'transaction_id', 'provider_details',
            'processed_at', 'created_at', 'updated_at', 'payment_count'
        ]
    
    def get_instructor_name(self, obj):
        return f"{obj.instructor.first_name} {obj.instructor.last_name}".strip() or obj.instructor.email


class PayoutRequestSerializer(serializers.Serializer):
    """Serializer for requesting payouts"""
    
    amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2,
        min_value=Decimal('10.00'),
        required=False
    )
    payout_method = serializers.ChoiceField(
        choices=Payout.METHOD_CHOICES,
        default='stripe_connect'
    )
    account_details = serializers.JSONField(required=False)


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for Refund model"""
    
    payment_id = serializers.IntegerField(source='payment.id', read_only=True)
    payment_amount = serializers.DecimalField(
        source='payment.amount',
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    requested_by_email = serializers.EmailField(source='requested_by.email', read_only=True, allow_null=True)
    processed_by_email = serializers.EmailField(source='processed_by.email', read_only=True, allow_null=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 'payment', 'payment_id', 'payment_amount',
            'requested_by', 'requested_by_email',
            'processed_by', 'processed_by_email',
            'amount', 'refund_type', 'reason', 'status',
            'admin_notes', 'rejection_reason',
            'provider_refund_id',
            'requested_at', 'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'processed_by', 'status', 'admin_notes', 'rejection_reason',
            'provider_refund_id', 'requested_at', 'processed_at',
            'created_at', 'updated_at'
        ]


class RefundRequestSerializer(serializers.Serializer):
    """Serializer for requesting refunds"""
    
    payment_id = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    reason = serializers.CharField(max_length=1000)
    refund_type = serializers.ChoiceField(
        choices=Refund.REFUND_TYPE_CHOICES,
        default='full'
    )


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for Coupon model"""
    
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True, allow_null=True)
    is_valid = serializers.BooleanField(read_only=True)
    usage_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'discount_type', 'discount_value',
            'applies_to', 'specific_courses', 'specific_events',
            'max_discount_amount', 'min_order_amount',
            'usage_limit', 'usage_limit_per_user', 'current_usage',
            'is_active', 'is_valid',
            'valid_from', 'expires_at',
            'created_by', 'created_by_email', 'usage_stats',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'current_usage', 'is_valid', 'usage_stats',
            'created_at', 'updated_at'
        ]
    
    def get_usage_stats(self, obj):
        from payments.services import get_coupon_usage_stats
        return get_coupon_usage_stats(obj)


class CouponCreateSerializer(serializers.Serializer):
    """Serializer for creating coupons"""
    
    code = serializers.CharField(max_length=64)
    discount_type = serializers.ChoiceField(choices=Coupon.TYPE_CHOICES)
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    applies_to = serializers.ChoiceField(choices=Coupon.APPLIES_TO_CHOICES, default='all')
    specific_course_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    specific_event_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    max_discount_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    min_order_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    usage_limit = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    usage_limit_per_user = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    valid_from = serializers.DateTimeField(required=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)


class CouponValidationSerializer(serializers.Serializer):
    """Serializer for validating coupons"""
    
    code = serializers.CharField(max_length=64)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    course_id = serializers.IntegerField(required=False, allow_null=True)
    event_id = serializers.IntegerField(required=False, allow_null=True)


class CouponRedemptionSerializer(serializers.ModelSerializer):
    """Serializer for Coupon Redemption"""
    
    coupon_code = serializers.CharField(source='coupon.code', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = CouponRedemption
        fields = [
            'id', 'coupon', 'coupon_code',
            'user', 'user_email',
            'payment', 'discount_amount', 'redeemed_at'
        ]
        read_only_fields = ['id', 'redeemed_at']


class PaymentDisputeSerializer(serializers.ModelSerializer):
    """Serializer for Payment Dispute"""
    
    payment_id = serializers.IntegerField(source='payment.id', read_only=True)
    
    class Meta:
        model = PaymentDispute
        fields = [
            'id', 'payment', 'payment_id', 'dispute_id',
            'amount', 'currency', 'reason', 'status',
            'evidence', 'admin_notes',
            'opened_at', 'closed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'dispute_id', 'opened_at', 'closed_at',
            'created_at', 'updated_at'
        ]


class PaymentStatsSerializer(serializers.Serializer):
    """Serializer for payment statistics"""
    
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_refunded = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_platform_fees = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_instructor_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_transactions = serializers.IntegerField()
    completed_transactions = serializers.IntegerField()
    failed_transactions = serializers.IntegerField()
    success_rate = serializers.FloatField()
    by_payment_method = serializers.ListField()


class InstructorBalanceSerializer(serializers.Serializer):
    """Serializer for instructor balance"""
    
    total_earnings = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_out = serializers.DecimalField(max_digits=12, decimal_places=2)
    pending = serializers.DecimalField(max_digits=12, decimal_places=2)
    available = serializers.DecimalField(max_digits=12, decimal_places=2)
