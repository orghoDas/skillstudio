"""
Payment Admin Configuration
Django admin interface for payment models
"""

from django.contrib import admin
from django.utils.html import format_html
from payments.models import (
    Payment, Payout, Refund, Coupon, CouponRedemption,
    PaymentGatewayConfig, PaymentWebhookLog, PaymentDispute
)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'user_email', 'amount_display', 'status_display',
        'payment_method', 'item_display', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'created_at']
    search_fields = ['user__email', 'provider_id', 'billing_email']
    readonly_fields = [
        'id', 'user', 'instructor', 'course',  # Removed 'event' - events app disabled
        'platform_fee', 'instructor_earnings', 'provider_id',
        'created_at', 'updated_at', 'completed_at'
    ]
    date_hierarchy = 'created_at'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'
    
    def amount_display(self, obj):
        return f"${obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'gray',
            'disputed': 'purple',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'
    
    def item_display(self, obj):
        if obj.course:
            return f"Course: {obj.course.title}"
        # Removed event reference - events app disabled
        return "N/A"
    item_display.short_description = 'Item'


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'instructor_email', 'amount_display', 'status_display',
        'payout_method', 'created_at'
    ]
    list_filter = ['status', 'payout_method', 'created_at']
    search_fields = ['instructor__email', 'transaction_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'processed_at']
    date_hierarchy = 'created_at'
    filter_horizontal = ['payments']
    
    def instructor_email(self, obj):
        return obj.instructor.email
    instructor_email.short_description = 'Instructor'
    
    def amount_display(self, obj):
        return f"${obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'paid': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'payment_id', 'amount_display', 'refund_type',
        'status_display', 'requested_by_email', 'created_at'
    ]
    list_filter = ['status', 'refund_type', 'created_at']
    search_fields = ['payment__id', 'requested_by__email', 'reason']
    readonly_fields = [
        'id', 'payment', 'requested_by', 'requested_at',
        'created_at', 'updated_at', 'processed_at'
    ]
    date_hierarchy = 'created_at'
    
    def payment_id(self, obj):
        return obj.payment.id
    payment_id.short_description = 'Payment ID'
    
    def requested_by_email(self, obj):
        return obj.requested_by.email if obj.requested_by else 'N/A'
    requested_by_email.short_description = 'Requested By'
    
    def amount_display(self, obj):
        return f"${obj.amount}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'requested': 'orange',
            'approved': 'blue',
            'processed': 'green',
            'rejected': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        'code', 'discount_display', 'is_active', 'is_valid',
        'usage_display', 'expires_at', 'created_at'
    ]
    list_filter = ['is_active', 'discount_type', 'applies_to', 'created_at']
    search_fields = ['code']
    readonly_fields = ['id', 'current_usage', 'is_valid', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    filter_horizontal = ['specific_courses']  # Removed 'specific_events' - events app disabled
    
    def discount_display(self, obj):
        if obj.discount_type == Coupon.PERCENT:
            return f"{obj.discount_value}%"
        return f"${obj.discount_value}"
    discount_display.short_description = 'Discount'
    
    def usage_display(self, obj):
        if obj.usage_limit:
            return f"{obj.current_usage} / {obj.usage_limit}"
        return str(obj.current_usage)
    usage_display.short_description = 'Usage'


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ['id', 'coupon_code', 'user_email', 'discount_amount', 'redeemed_at']
    list_filter = ['redeemed_at']
    search_fields = ['coupon__code', 'user__email']
    readonly_fields = ['id', 'coupon', 'user', 'payment', 'redeemed_at']
    date_hierarchy = 'redeemed_at'
    
    def coupon_code(self, obj):
        return obj.coupon.code
    coupon_code.short_description = 'Coupon'
    
    def user_email(self, obj):
        return obj.user.email
    user_email.short_description = 'User'


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ['gateway_name', 'is_active', 'mode_display', 'created_at']
    list_filter = ['is_active', 'is_test_mode', 'gateway_name']
    readonly_fields = ['created_at', 'updated_at']
    
    def mode_display(self, obj):
        if obj.is_test_mode:
            return format_html('<span style="color: orange;">TEST MODE</span>')
        return format_html('<span style="color: green;">LIVE MODE</span>')
    mode_display.short_description = 'Mode'


@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'gateway', 'event_type', 'event_id',
        'processed_display', 'payment_id', 'created_at'
    ]
    list_filter = ['gateway', 'processed', 'created_at']
    search_fields = ['event_id', 'event_type']
    readonly_fields = ['id', 'gateway', 'event_type', 'event_id', 'payload', 'created_at', 'processed_at']
    date_hierarchy = 'created_at'
    
    def payment_id(self, obj):
        return obj.payment.id if obj.payment else 'N/A'
    payment_id.short_description = 'Payment'
    
    def processed_display(self, obj):
        if obj.processed:
            return format_html('<span style="color: green;">✓ Processed</span>')
        return format_html('<span style="color: orange;">Pending</span>')
    processed_display.short_description = 'Status'


@admin.register(PaymentDispute)
class PaymentDisputeAdmin(admin.ModelAdmin):
    list_display = [
        'dispute_id', 'payment_id', 'amount_display',
        'status_display', 'opened_at'
    ]
    list_filter = ['status', 'opened_at']
    search_fields = ['dispute_id', 'payment__id']
    readonly_fields = ['id', 'payment', 'dispute_id', 'opened_at', 'created_at', 'updated_at']
    date_hierarchy = 'opened_at'
    
    def payment_id(self, obj):
        return obj.payment.id
    payment_id.short_description = 'Payment ID'
    
    def amount_display(self, obj):
        return f"${obj.amount} {obj.currency}"
    amount_display.short_description = 'Amount'
    
    def status_display(self, obj):
        colors = {
            'opened': 'orange',
            'under_review': 'blue',
            'won': 'green',
            'lost': 'red',
            'closed': 'gray',
        }
        color = colors.get(obj.status, 'black')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.status.upper()
        )
    status_display.short_description = 'Status'
