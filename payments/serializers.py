"""
Payment Serializers
Serializers for payment-related models
"""

from rest_framework import serializers
from decimal import Decimal
from payments.models import Payment, Payout, Refund, Coupon
from courses.models import Course
from accounts.utils import public_instructor_name


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    
    user_email = serializers.EmailField(source='user.email', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True, allow_null=True)
    course_slug = serializers.CharField(source='course.slug', read_only=True, allow_null=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'purpose', 'user', 'user_email', 'instructor',
            'course', 'course_title', 'course_slug',
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


class PayoutSerializer(serializers.ModelSerializer):
    """Serializer for Payout model"""
    
    instructor_email = serializers.EmailField(source='instructor.email', read_only=True)
    instructor_name = serializers.SerializerMethodField()
    payment_count = serializers.IntegerField(read_only=True)
    account_details = serializers.SerializerMethodField()
    
    class Meta:
        model = Payout
        fields = [
            'id', 'instructor', 'instructor_email', 'instructor_name',
            'amount', 'currency', 'payment_count',
            'status', 'wallet_debited', 'payout_method', 'account_details',
            'transaction_id', 'provider_details',
            'failure_reason', 'admin_notes',
            'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'transaction_id', 'provider_details', 'wallet_debited',
            'processed_at', 'created_at', 'updated_at', 'payment_count'
        ]
    
    def get_instructor_name(self, obj) -> str:
        return public_instructor_name(obj.instructor)

    def get_account_details(self, obj) -> dict:
        return {'provided': True} if obj.account_details_encrypted else {}


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
            'instructor_debit', 'platform_absorbed',
            'admin_notes', 'rejection_reason',
            'provider_refund_id',
            'requested_at', 'processed_at', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'processed_by', 'status', 'admin_notes', 'rejection_reason',
            'instructor_debit', 'platform_absorbed', 'refund_type',
            'provider_refund_id', 'requested_at', 'processed_at',
            'created_at', 'updated_at'
        ]


class RefundRequestSerializer(serializers.Serializer):
    """Request a refund of a course purchase.

    ``amount`` is optional and defaults to everything still refundable; the
    full/partial type is derived server-side.
    """

    payment_id = serializers.IntegerField()
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal('0.01'), required=False, allow_null=True
    )
    reason = serializers.CharField(max_length=1000)


class CouponSerializer(serializers.ModelSerializer):
    """Serializer for Coupon model"""
    
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True, allow_null=True)
    is_valid = serializers.BooleanField(read_only=True)
    usage_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Coupon
        fields = [
            'id', 'code', 'discount_type', 'discount_value',
            'applies_to', 'specific_courses',
            'max_discount_amount', 'min_order_amount',
            'usage_limit', 'usage_limit_per_user', 'current_usage',
            'is_active', 'is_public', 'is_valid',
            'valid_from', 'expires_at',
            'created_by', 'created_by_email', 'usage_stats',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'current_usage', 'is_valid', 'usage_stats',
            'created_at', 'updated_at'
        ]
    
    def get_usage_stats(self, obj) -> dict:
        from payments.services import get_coupon_usage_stats
        return get_coupon_usage_stats(obj)


class PublicCouponSerializer(serializers.ModelSerializer):
    """What a student may see about a coupon (no usage stats or admin data)."""

    class Meta:
        model = Coupon
        fields = [
            'code', 'discount_type', 'discount_value', 'applies_to',
            'max_discount_amount', 'min_order_amount', 'expires_at',
        ]
        read_only_fields = fields


class CouponCreateSerializer(serializers.Serializer):
    """Serializer for creating coupons"""
    
    code = serializers.CharField(max_length=64)
    discount_type = serializers.ChoiceField(choices=Coupon.TYPE_CHOICES)
    discount_value = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    applies_to = serializers.ChoiceField(choices=Coupon.APPLIES_TO_CHOICES, default='all')
    specific_course_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=2**63 - 1),
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
    usage_limit = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=2**31 - 1)
    usage_limit_per_user = serializers.IntegerField(required=False, allow_null=True, min_value=1, max_value=2**31 - 1)
    valid_from = serializers.DateTimeField(required=False)
    expires_at = serializers.DateTimeField(required=False, allow_null=True)
    is_active = serializers.BooleanField(default=True)
    is_public = serializers.BooleanField(default=False)

    def validate_specific_course_ids(self, value):
        found = set(Course.objects.filter(id__in=value).values_list('id', flat=True))
        missing = sorted(set(value) - found)
        if missing:
            raise serializers.ValidationError(f"Unknown course id(s): {missing}")
        return value

    def validate(self, attrs):
        if attrs.get('applies_to') == 'specific' and not attrs.get('specific_course_ids'):
            raise serializers.ValidationError(
                {'specific_course_ids': "Required when applies_to is 'specific'."}
            )
        return attrs


class CouponValidationSerializer(serializers.Serializer):
    """Check a coupon against a course. The price always comes from the server."""

    code = serializers.CharField(max_length=64)
    course_id = serializers.IntegerField()


class PaymentDateRangeSerializer(serializers.Serializer):
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        start, end = attrs.get('start_date'), attrs.get('end_date')
        if start and end and start > end:
            raise serializers.ValidationError({'end_date': 'The end date must not precede the start date.'})
        return attrs


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
